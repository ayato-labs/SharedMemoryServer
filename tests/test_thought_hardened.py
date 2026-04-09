import aiosqlite
import pytest

from shared_memory import thought_logic
from shared_memory.thought_logic import get_thought_history, process_thought_core
from shared_memory.utils import get_thoughts_db_path


@pytest.fixture(autouse=True)
async def init_hardened_db(mock_env):
    """Initializes the thoughts database and clears history for isolation."""
    await thought_logic.init_thoughts_db()

    # Clear history to ensure test isolation
    async with aiosqlite.connect(get_thoughts_db_path()) as conn:
        await conn.execute("DELETE FROM thought_history")
        await conn.commit()


@pytest.mark.asyncio
async def test_sensitive_data_masking_in_thoughts():
    """
    Ensures that sensitive data like API keys are masked BEFORE being saved to the thoughts database.
    """
    secret_key = "sk-ant-api03-1234567890abcdef1234567890abcdef-12345"
    thought_content = f"I am using the API key {secret_key} to perform a task."

    await process_thought_core(
        thought=thought_content,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id="security_session",
    )

    # Retrieve from DB and verify masking
    history = await get_thought_history("security_session")
    saved_thought = history[0]["thought"]

    assert secret_key not in saved_thought
    assert "[API_KEY_MASKED]" in saved_thought


@pytest.mark.asyncio
async def test_invalid_revision_validation():
    """
    Ensures that revising a non-existent thought returns a proper error.
    """
    result = await process_thought_core(
        thought="Revising something that doesn't exist",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        is_revision=True,
        revises_thought=99,  # Non-existent
        session_id="validation_session",
    )

    assert "error" in result
    assert "Invalid revision" in result["error"]
    assert "Thought #99 does not exist" in result["error"]


@pytest.mark.asyncio
async def test_performance_with_indices(benchmark=None):
    """
    Verification of index presence (indirectly through successful initialization).
    Also ensures multiple thoughts are stored correctly.
    """
    for i in range(1, 11):
        await process_thought_core(
            thought=f"Step {i}",
            thought_number=i,
            total_thoughts=10,
            next_thought_needed=(i < 10),
            session_id="perf_session",
        )

    history = await get_thought_history("perf_session")
    assert len(history) == 10
    assert history[9]["thought_number"] == 10
