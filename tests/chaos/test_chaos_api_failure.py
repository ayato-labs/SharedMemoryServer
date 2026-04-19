import pytest
from unittest.mock import MagicMock
from shared_memory import logic, graph
from shared_memory.exceptions import DatabaseError

@pytest.mark.asyncio
async def test_chaos_api_timeout_handling(mock_llm):
    """
    Chaos Test: Verify that the system handles LLM API timeouts gracefully.
    It should log the error and return a sensible result instead of crashing.
    """
    # Simulate timeout in the mock
    mock_llm.models.generate_content.side_effect = Exception("Deadline Exceeded (Simulation)")
    
    # We test conflict check which uses generate_content
    is_conflict, reason = await graph.check_conflict("TimeoutEntity", "Should handle error", "agent1")
    
    # It should return a default "no conflict" or "error handled" state
    assert is_conflict is False
    assert reason is None

@pytest.mark.asyncio
async def test_chaos_api_malformed_json_response(mock_llm):
    """
    Chaos Test: Verify that the system handles malformed JSON from the LLM.
    """
    # Mock LLM returns invalid JSON string
    mock_llm.models.generate_content.return_value.text = "NOT A JSON { ["
    
    # Conflict check tries to parse the JSON
    is_conflict, reason = await graph.check_conflict("MalformedEntity", "Should handle error", "agent1")
    
    assert is_conflict is False # Fallback to safe state
    assert reason is None
