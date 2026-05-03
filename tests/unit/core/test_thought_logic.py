from unittest.mock import patch

import pytest

from shared_memory.core.thought_logic import process_thought_core


@pytest.mark.asyncio
async def test_process_thought_persistence(fake_llm_client):
    """Verify thought process persists to database."""
    # Mock LLM is used in background distillation or synchronous salvage
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        result = await process_thought_core(
            thought="Thinking about architecture.",
            thought_number=1,
            total_thoughts=5,
            next_thought_needed=True,
            session_id="test_session",
        )

        assert result["thoughtNumber"] == 1
        assert result["totalThoughts"] == 5
        assert result["nextThoughtNeeded"] is True

        # Verify in DB
        from shared_memory.core.thought_logic import get_thought_history

        history = await get_thought_history("test_session")
        assert len(history) == 1
        assert history[0]["thought"] == "Thinking about architecture."


@pytest.mark.asyncio
async def test_process_thought_none_session(fake_llm_client):
    """Verify thought process handles None session_id by using default."""
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        # We pass None explicitly, which previously caused IntegrityError
        result = await process_thought_core(
            thought="Thinking with None session.",
            thought_number=1,
            total_thoughts=1,
            next_thought_needed=False,
            session_id=None,
        )

        assert result["thoughtNumber"] == 1
        assert result["totalThoughts"] == 1

        # Verify it persisted as 'default_session'
        from shared_memory.core.thought_logic import get_thought_history

        history = await get_thought_history("default_session")
        assert any(h["thought"] == "Thinking with None session." for h in history)
