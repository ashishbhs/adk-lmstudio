"""
research_agents.py — Three-agent deep research pipeline.

Architecture (SequentialAgent):
  1. PlannerAgent    — Decomposes the query into targeted sub-queries
  2. ExecutorAgent   — Runs Google searches & fetches page content
  3. SynthesizerAgent — Synthesises all findings into a deep report

Each agent uses the LM Studio LLM via LiteLLM.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from local_adk.llm import get_local_model
from local_adk.logger import setup_logger
from local_adk.tools.search_tools import google_search, fetch_page

logger = setup_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Agent 1 — Planner
# Receives the user query and outputs a structured research plan with
# 3-5 distinct Google search queries.
# ──────────────────────────────────────────────────────────────────────────────
PLANNER_INSTRUCTION = """
You are ResearchPlanner, an expert at decomposing research questions into
precise, targeted Google search queries.

When given a user's research topic or question, you must:
1. Identify 3 to 5 distinct sub-aspects of the topic that need investigation.
2. For each aspect, craft a specific, optimised Google search query.
3. Return ONLY a structured JSON block (no other text) in this exact format:

```json
{
  "research_plan": {
    "topic": "<user topic>",
    "queries": [
      "<search query 1>",
      "<search query 2>",
      "<search query 3>"
    ]
  }
}
```

Be specific. Use advanced search syntax (quotes, site:, filetype:) when helpful.
Do NOT explain your reasoning. Do NOT output a "Thinking Process". Output ONLY the raw JSON block and nothing else.
""".strip()

# ──────────────────────────────────────────────────────────────────────────────
# Agent 2 — Executor
# Reads the planner's JSON plan, executes each search, fetches top pages,
# and compiles raw evidence.
# ──────────────────────────────────────────────────────────────────────────────
EXECUTOR_INSTRUCTION = """
You are ResearchExecutor, an autonomous web researcher.

You will receive a research plan JSON from ResearchPlanner. Your job is to:
1. Parse the JSON to extract all search queries.
2. For EACH query, call the `google_search` tool to get results.
3. For the TOP 2 results of each query, call `fetch_page` to get detailed content.
4. Compile all findings into a structured evidence report.

Output format — after all tool calls are complete, return a structured markdown
evidence report with these sections:

## Evidence Report

### Query: <query text>
**Source 1:** [<title>](<url>)
> <key findings from the page>

**Source 2:** [<title>](<url>)
> <key findings from the page>

---

Repeat for every query. Be thorough. Include ALL relevant facts, numbers,
dates, quotes, and technical details you find. Do NOT summarise yet —
preserve raw details for the synthesiser.
""".strip()

# ──────────────────────────────────────────────────────────────────────────────
# Agent 3 — Synthesizer
# Receives the evidence report and produces a comprehensive deep-research output.
# ──────────────────────────────────────────────────────────────────────────────
SYNTHESIZER_INSTRUCTION = """
You are ResearchSynthesizer, an expert analyst and technical writer.

You will receive an Evidence Report compiled by ResearchExecutor.
Your task is to synthesise all evidence into a COMPREHENSIVE DEEP RESEARCH REPORT.

The report MUST include:

# 🔍 Deep Research Report: <Topic>

## Executive Summary
A concise 2-3 paragraph overview of the most important findings.

## Key Findings
Bullet-pointed list of the most significant facts, data points, and insights.

## Detailed Analysis
### <Sub-topic 1>
In-depth discussion with evidence citations [source name](url).

### <Sub-topic 2>
...continue for each major sub-topic...

## Conflicting Views / Limitations
Note any contradictions, gaps, or contested information found.

## Conclusion
Synthesised conclusion with actionable takeaways.

## Sources
Numbered list of all URLs cited.

---
Rules:
- Use clear, professional language.
- Cite sources inline with [text](url) markdown links.
- Use tables, bullet points, and headers to improve readability.
- Be comprehensive — this is a deep research report, not a summary.
- Minimum length: 800 words.
- Do NOT include any internal "Thinking Process" or `<think>` tags in your final output. Start directly with the report.
""".strip()


def create_planner_agent() -> LlmAgent:
    """Creates the Planner agent."""
    logger.info("Creating PlannerAgent")
    return LlmAgent(
        name="PlannerAgent",
        model=get_local_model(),
        instruction=PLANNER_INSTRUCTION,
        description="Decomposes research queries into targeted Google search plans.",
    )


def create_executor_agent() -> LlmAgent:
    """Creates the Executor agent with search tools."""
    logger.info("Creating ExecutorAgent")
    return LlmAgent(
        name="ExecutorAgent",
        model=get_local_model(),
        instruction=EXECUTOR_INSTRUCTION,
        description="Executes Google searches and fetches web page content.",
        tools=[google_search, fetch_page],
    )


def create_synthesizer_agent() -> LlmAgent:
    """Creates the Synthesizer agent."""
    logger.info("Creating SynthesizerAgent")
    return LlmAgent(
        name="SynthesizerAgent",
        model=get_local_model(),
        instruction=SYNTHESIZER_INSTRUCTION,
        description="Synthesises research evidence into comprehensive reports.",
    )


def create_research_pipeline() -> SequentialAgent:
    """
    Creates the full 3-agent deep research pipeline:
    PlannerAgent → ExecutorAgent → SynthesizerAgent
    """
    logger.info("Creating DeepResearch SequentialAgent pipeline")
    return SequentialAgent(
        name="DeepResearchPipeline",
        description=(
            "A 3-agent pipeline that plans Google searches, executes them, "
            "and synthesises a comprehensive deep research report."
        ),
        sub_agents=[
            create_planner_agent(),
            create_executor_agent(),
            create_synthesizer_agent(),
        ],
    )
