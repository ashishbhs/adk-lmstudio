class ADKServiceError(Exception):
    """Base exception for all local ADK service errors."""
    pass

class LLMConnectionError(ADKServiceError):
    """Raised when the connection to the LM Studio server fails."""
    pass

class AgentExecutionError(ADKServiceError):
    """Raised when the ADK runner encounters an execution error."""
    pass
