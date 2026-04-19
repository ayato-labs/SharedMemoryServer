import pytest

from shared_memory import graph


@pytest.mark.asyncio
async def test_chaos_api_timeout_handling(mock_llm):
    """
    Chaos Test: Artificially inject an Exception into generating content to
    simulate a network timeout or API failure.
    """
    # Simulate timeout in the mock
    mock_llm.models.generate_content.side_effect = Exception("Deadline Exceeded (Simulation)")

    # We test conflict check which uses generate_content
    is_conflict, reason = await graph.check_conflict(
        "TimeoutEntity", "Should handle error", "agent1"
    )

    # It should return a default "no conflict" or "error handled" state
    assert is_conflict is False


@pytest.mark.asyncio
async def test_chaos_api_malformed_json_response(mock_llm):
    """
    Chaos Test: Simulate the LLM returning malformed JSON and ensure the
    conflict check handles it gracefully.
    """
    # Mock LLM returns invalid JSON string
    mock_llm.models.generate_content.return_value.text = "NOT A JSON { ["

    # Conflict check tries to parse the JSON
    is_conflict, reason = await graph.check_conflict(
        "MalformedEntity", "Should handle error", "agent1"
    )

    assert is_conflict is False  # Fallback to safe state
    assert reason is None
