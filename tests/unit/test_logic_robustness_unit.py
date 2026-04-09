from unittest.mock import patch

import pytest

from shared_memory.logic import save_memory_core
from tests.unit.fake_client import FakeGeminiClient, FakeGeminiResponse


@pytest.mark.asyncio
async def test_logic_handles_malformed_llm_json_unit(mock_env):
    """
    Unit test: Verify that save_memory_core doesn't crash if LLM returns garbage JSON.
    Uses FakeGeminiClient with high-level logic.
    """
    fake_client = FakeGeminiClient()
    # Inject malformed JSON text
    fake_client.models.generate_content = lambda *args, **kwargs: FakeGeminiResponse(
        text="INVALID_JSON"
    )

    with patch("shared_memory.graph.get_gemini_client", return_value=fake_client):
        entities = [{"name": "RobustEntity", "description": "Test"}]
        # This should not raise an exception, but handle the parse error gracefully
        res = await save_memory_core(entities=entities)
        assert "Saved" in res

@pytest.mark.asyncio
async def test_logic_api_failure_resilience_unit(mock_env):
    """
    Unit test: Verify system resilience when Gemini API raises an exception.
    """
    fake_client = FakeGeminiClient()
    fake_client.models.set_error("embed_content", Exception("API Connectivity Issue"))

    with patch("shared_memory.embeddings.get_gemini_client", return_value=fake_client):
        entities = [{"name": "ResilientEntity", "description": "Test"}]
        # Should still save to DB even if embeddings fail
        res = await save_memory_core(entities=entities)
        assert "Saved" in res

@pytest.mark.asyncio
async def test_logic_partial_success_unit(mock_env):
    """
    Unit test: Verify that some items are saved even if others fail validation.
    """
    # 1 valid, 1 invalid (missing name)
    entities = [
        {"name": "ValidEntity", "description": "Save me"},
        {"description": "I have no name"}
    ]

    res = await save_memory_core(entities=entities)
    assert "Saved 1 entities" in res
    assert "Errors: 1" in res
