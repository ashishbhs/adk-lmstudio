import pytest
from unittest.mock import MagicMock, patch
from google.adk.models.lite_llm import LiteLlm
from local_adk.agent import create_specialist_agent

@patch("local_adk.agent.get_local_model")
def test_create_specialist_agent(mock_get_model):
    # Arrange
    mock_model = MagicMock(spec=LiteLlm)
    mock_get_model.return_value = mock_model

    # Act
    agent = create_specialist_agent()

    # Assert
    assert agent.name == "LocalSpecialist"
    assert agent.model == mock_model
    assert "expert software engineering assistant" in agent.instruction
    mock_get_model.assert_called_once()
