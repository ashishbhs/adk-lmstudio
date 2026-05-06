"""
FastAPI server exposing the Local ADK multi-agent system via HTTP/SSE.
Run with: poetry run python -m local_adk.server
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from local_adk.agent import create_specialist_agent
from local_adk.research_agents import create_research_pipeline
from local_adk.config import config
from local_adk.exceptions import ADKServiceError
from local_adk.logger import setup_logger

logger = setup_logger(__name__)

APP_NAME = "LocalADKService"

# ---------------------------------------------------------------------------
# Global singletons (initialised at startup)
# ---------------------------------------------------------------------------
session_service: InMemorySessionService | None = None
runners: dict[str, Runner] = {}

AGENTS_REGISTRY = [
    {
        "id": "local-specialist",
        "name": "LocalSpecialist",
        "role": "Software Engineering Expert",
        "description": "Precise, accurate technical responses on any engineering topic.",
        "model": config.model_name,
        "status": "online",
        "color": "#06b6d4",
    },
    {
        "id": "code-reviewer",
        "name": "CodeReviewer",
        "role": "Code Review & Quality",
        "description": "Analyses code for bugs, performance, and best practices.",
        "model": config.model_name,
        "status": "standby",
        "color": "#a855f7",
    },
    {
        "id": "doc-writer",
        "name": "DocWriter",
        "role": "Documentation Specialist",
        "description": "Generates clean, readable technical documentation.",
        "model": config.model_name,
        "status": "standby",
        "color": "#22d3ee",
    },
    # ── Deep Research pipeline (SequentialAgent) ───────────────────────────
    {
        "id": "deep-research",
        "name": "DeepResearch",
        "role": "Deep Research Pipeline",
        "description": "3-agent pipeline: Planner → Executor (Google Search) → Synthesizer.",
        "model": config.model_name,
        "status": "online",
        "color": "#f59e0b",
        "pipeline": [
            {"id": "planner",     "name": "PlannerAgent",     "color": "#6366f1"},
            {"id": "executor",   "name": "ExecutorAgent",    "color": "#22c55e"},
            {"id": "synthesizer","name": "SynthesizerAgent", "color": "#f59e0b"},
        ],
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service
    logger.info("Initialising LocalADK service...")
    session_service = InMemorySessionService()

    # Pre-warm the primary agent runner
    agent = create_specialist_agent()
    runners["local-specialist"] = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Pre-warm the deep research pipeline runner
    research_pipeline = create_research_pipeline()
    runners["deep-research"] = Runner(
        agent=research_pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    logger.info("Service ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(title="Local ADK UI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    agent_id: str = "local-specialist"
    session_id: str | None = None
    user_id: str = "local-user"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Quick health check — also verifies LM Studio reachability."""
    import httpx
    lm_status = "offline"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(config.llm_base_url.rstrip("/v1").rstrip("/") + "/v1/models")
            if r.status_code == 200:
                lm_status = "online"
    except Exception:
        pass
    return {
        "status": "ok",
        "lm_studio": lm_status,
        "model": config.model_name,
        "base_url": config.llm_base_url,
    }


@app.get("/api/agents")
async def get_agents():
    return {"agents": AGENTS_REGISTRY}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Returns a Server-Sent Events stream of the agent response."""

    async def event_generator() -> AsyncGenerator[str, None]:
        runner = runners.get(req.agent_id)
        if runner is None:
            yield f"data: {json.dumps({'error': f'Agent {req.agent_id!r} not found or not initialised.'})}\n\n"
            return

        sid = req.session_id or str(uuid.uuid4())

        try:
            # Ensure session exists
            existing = await session_service.get_session(
                app_name=APP_NAME, user_id=req.user_id, session_id=sid
            )
            if existing is None:
                await session_service.create_session(
                    app_name=APP_NAME, user_id=req.user_id, session_id=sid
                )

            new_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=req.message)],
            )

            # Yield session_id first so the client can track multi-turn
            yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

            # Use run_async — native async generator, no thread executor needed
            full_text = ""
            async for event in runner.run_async(
                user_id=req.user_id,
                session_id=sid,
                new_message=new_message,
            ):
                logger.debug(f"Event received: is_final={event.is_final_response()}, has_content={bool(event.content)}")
                # Accumulate text from the final model response event
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            full_text += part.text

            if not full_text:
                logger.warning("run_async completed but no text was produced.")
                yield f"data: {json.dumps({'type': 'error', 'text': 'No response received from model.'})}\n\n"
                return

            # Stream the response word-by-word for a typing effect
            words = full_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                await asyncio.sleep(0.015)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except ADKServiceError as e:
            logger.error(f"ADK error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        except Exception as e:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Deep Research stream endpoint
# Emits per-agent progress events so the UI can show the pipeline stages.
# ---------------------------------------------------------------------------
class ResearchRequest(BaseModel):
    query: str
    session_id: str | None = None
    user_id: str = "local-user"


@app.post("/api/research/stream")
async def research_stream(req: ResearchRequest):
    """SSE stream for the deep research pipeline (Planner→Executor→Synthesizer)."""

    async def event_generator() -> AsyncGenerator[str, None]:
        runner = runners.get("deep-research")
        if runner is None:
            yield f"data: {json.dumps({'type': 'error', 'text': 'Research pipeline not initialised.'})}\n\n"
            return

        sid = req.session_id or str(uuid.uuid4())

        try:
            existing = await session_service.get_session(
                app_name=APP_NAME, user_id=req.user_id, session_id=sid
            )
            if existing is None:
                await session_service.create_session(
                    app_name=APP_NAME, user_id=req.user_id, session_id=sid
                )

            new_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=req.query)],
            )

            yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"
            yield f"data: {json.dumps({'type': 'pipeline_start', 'stages': ['PlannerAgent', 'ExecutorAgent', 'SynthesizerAgent']})}\n\n"

            # Track which pipeline stage we are in by watching the author field
            STAGE_ORDER = ["PlannerAgent", "ExecutorAgent", "SynthesizerAgent"]
            current_stage: str | None = None
            final_text = ""
            stage_outputs: dict[str, str] = {}

            async for event in runner.run_async(
                user_id=req.user_id,
                session_id=sid,
                new_message=new_message,
            ):
                author = getattr(event, 'author', None)
                is_final = event.is_final_response()

                # Emit stage transition
                if author and author in STAGE_ORDER and author != current_stage:
                    if current_stage:
                        # Emit previous stage completion
                        yield f"data: {json.dumps({'type': 'stage_complete', 'stage': current_stage})}\n\n"
                    current_stage = author
                    yield f"data: {json.dumps({'type': 'stage_start', 'stage': author})}\n\n"

                # Tool call events — inform UI which tool is running
                if hasattr(event, 'get_function_calls') and event.get_function_calls():
                    for fn_call in event.get_function_calls():
                        tool_name = getattr(fn_call, 'name', 'tool')
                        tool_args = getattr(fn_call, 'args', {})
                        query_arg = tool_args.get('query', tool_args.get('url', ''))
                        yield f"data: {json.dumps({'type': 'tool_call', 'stage': current_stage, 'tool': tool_name, 'arg': str(query_arg)[:120]})}\n\n"

                # Capture final output per stage
                if is_final and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            if current_stage:
                                stage_outputs[current_stage] = stage_outputs.get(current_stage, '') + part.text
                                if current_stage == "SynthesizerAgent":
                                    final_text += part.text
                            else:
                                final_text += part.text

            # Emit final stage complete
            if current_stage:
                yield f"data: {json.dumps({'type': 'stage_complete', 'stage': current_stage})}\n\n"

            if not final_text:
                yield f"data: {json.dumps({'type': 'error', 'text': 'No research output was produced.'})}\n\n"
                return

            # Clean up reasoning blocks from local models (e.g., DeepSeek-R1 <think> tags)
            import re
            final_text = re.sub(r'<think>[\s\S]*?</think>\n*', '', final_text, flags=re.IGNORECASE)
            final_text = re.sub(r'\(Thinking Process:[\s\S]*?\)\n*', '', final_text, flags=re.IGNORECASE)
            final_text = final_text.strip()

            # Stream the synthesizer report word-by-word
            yield f"data: {json.dumps({'type': 'report_start'})}\n\n"
            words = final_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'type': 'done', 'stages_completed': list(stage_outputs.keys())})}\n\n"

        except Exception as e:
            logger.critical(f"Research pipeline error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Serve the UI (must be last to avoid catching API routes)
# ---------------------------------------------------------------------------
from pathlib import Path

UI_DIR  = Path(__file__).parent / "ui"
UI_FILE = UI_DIR / "index.html"

# Mount static assets (CSS, JS) — must come AFTER API routes
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    if not UI_FILE.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return HTMLResponse(content=UI_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("local_adk.server:app", host="0.0.0.0", port=8000, reload=True)
