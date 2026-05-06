from google.adk.models.lite_llm import LiteLlm
from local_adk.config import config
from local_adk.logger import setup_logger
from local_adk.exceptions import LLMConnectionError

logger = setup_logger(__name__)

def get_local_model() -> LiteLlm:
    """Instantiates the LiteLlm wrapper for LM Studio."""
    try:
        logger.debug(f"Loading model: {config.model_name}")
        return LiteLlm(model=config.model_name)
    except Exception as e:
        logger.error(f"Failed to initialize LiteLLM: {str(e)}")
        raise LLMConnectionError(f"Model initialization failed: {e}") from e
