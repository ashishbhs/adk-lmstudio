from google.adk.agents import LlmAgent
from local_adk.llm import get_local_model
from local_adk.logger import setup_logger

logger = setup_logger(__name__)

def create_specialist_agent() -> LlmAgent:
    """Creates and configures the ADK LlmAgent."""
    logger.info("Creating Local Specialist Agent")
    model = get_local_model()
    
    return LlmAgent(
        name="LocalSpecialist",
        model=model,
        instruction=(
            "You are an expert software engineering assistant operating locally. "
            "Provide precise, accurate, and structured technical responses."
        )
    )
