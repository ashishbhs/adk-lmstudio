import os
from dataclasses import dataclass
from local_adk.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class AppConfig:
    llm_base_url: str = os.getenv("OPENAI_API_BASE", "http://localhost:1234/v1")
    llm_api_key: str = os.getenv("OPENAI_API_KEY", "lm-studio")
    model_name: str = os.getenv("MODEL_NAME", "openai/google/gemma-4-e4b")

    def __post_init__(self):
        # Set environment variables required by LiteLLM globally
        os.environ["OPENAI_API_BASE"] = self.llm_base_url
        os.environ["OPENAI_API_KEY"] = self.llm_api_key
        logger.info(f"Initialized configuration targeting LM Studio at {self.llm_base_url}")

config = AppConfig()
