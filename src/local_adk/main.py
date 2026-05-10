import asyncio
import sys
import uuid
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from local_adk.agent import create_specialist_agent
from local_adk.logger import setup_logger
from local_adk.exceptions import ADKServiceError

logger = setup_logger(__name__)

APP_NAME = "LocalADKService"
USER_ID = "local-user"


async def run_query(query: str) -> None:
    try:
        agent = create_specialist_agent()
        session_service = InMemorySessionService()

        # Create a session for this conversation turn
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
        )

        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )

        # Build the message in the format ADK expects
        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

        logger.info(f"Executing query: '{query}'")

        # runner.run() is a synchronous generator of Events
        final_response = None
        for event in runner.run(
            user_id=USER_ID,
            session_id=session.id,
            new_message=new_message,
        ):
            # The last event with content from the model is the answer
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text

        logger.info("Execution successful.")
        if final_response:
            print(f"\nResponse:\n{final_response}\n")
        else:
            print("\nNo response content received.\n")

    except ADKServiceError as e:
        logger.error(f"Service Error encountered: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled system error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Entry point for the local-adk CLI."""
    import uvicorn
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        prompt = " ".join(sys.argv[2:]) or "Explain the mechanics of a vector database index."
        asyncio.run(run_query(prompt))
    else:
        logger.info("Starting Local ADK server via Uvicorn...")
        uvicorn.run("local_adk.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
