from unittest.mock import MagicMock, patch

import aiosqlite
import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.exceptions import DatabaseLockedError, SharedMemoryError
from shared_memory.logic import save_memory_core


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_save_memory_atomicity(mock_gemini):
    """
    Verify that if any part of save_memory fails (e.g. bank file write),
    the entire transaction is rolled back in the database.
    """
    entities = [{"name": "ShouldNotBeSaved", "description": "Crash testing"}]
    bank_files = {"crash.md": "Trigger a crash"}

    # 1. Mock save_bank_files to raise an exception
    with patch("shared_memory.bank.save_bank_files", side_effect=Exception("Disk Full")):
        with pytest.raises(SharedMemoryError) as excinfo:
            await save_memory_core(entities=entities, bank_files=bank_files)
        assert "Disk Full" in str(excinfo.value)

    # 2. Verify that 'ShouldNotBeSaved' is NOT in the database
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'ShouldNotBeSaved'")
        row = await cursor.fetchone()
        assert row is None


@pytest.mark.asyncio
async def test_llm_json_malformed_resilience(mock_gemini):
    """
    Verify that if the LLM returns non-JSON garbage, the system doesn't crash
    and handles it gracefully in conflict detection.
    """
    mock_gemini.models.generate_content.return_value = MagicMock(text="This is not JSON!")

    entities = [{"name": "RobustEntity", "description": "Testing parser"}]
    observations = [{"entity_name": "RobustEntity", "content": "This might trigger conflict logic"}]

    res = await save_memory_core(entities=entities, observations=observations)
    assert "Saved" in res

    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM observations WHERE entity_name = 'RobustEntity'")
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_db_lock_retry_simulation(mock_gemini):
    """
    Verify that the retry_on_db_lock decorator logic is triggered.
    Since retry_on_db_lock is now async, we need to test it accordingly.
    """
    from shared_memory.database import retry_on_db_lock

    mock_op = MagicMock()
    # Fail 2 times then succeed
    mock_op.side_effect = [
        aiosqlite.OperationalError("database is locked"),
        aiosqlite.OperationalError("database is locked"),
        "Success",
    ]

    @retry_on_db_lock(max_retries=5, initial_delay=0.01)
    async def test_func():
        return mock_op()

    res = await test_func()
    assert res == "Success"
    assert mock_op.call_count == 3


@pytest.mark.asyncio
async def test_db_lock_failure_raises_custom_exception(mock_gemini):
    """
    Verify that if retries are exhausted, DatabaseLockedError is raised.
    """
    from shared_memory.database import retry_on_db_lock

    mock_op = MagicMock()
    mock_op.side_effect = aiosqlite.OperationalError("database is locked")

    @retry_on_db_lock(max_retries=2, initial_delay=0.01)
    async def fail_func():
        return mock_op()

    with pytest.raises(DatabaseLockedError):
        await fail_func()
    assert mock_op.call_count == 2


@pytest.mark.asyncio
async def test_api_failure_resilience(mock_gemini):
    """
    Verify that if the Gemini API is completely down (raises exception),
    the system still saves the core data and doesn't crash the entire flow.
    """
    # Simulate a complete API failure
    mock_gemini.models.embed_content.side_effect = Exception("API Connection Failed")
    mock_gemini.models.generate_content.side_effect = Exception("API Connection Failed")

    entities = [{"name": "ResilientEntity", "entity_type": "Testing"}]
    observations = [{"entity_name": "ResilientEntity", "content": "Critical info"}]

    # The save should still succeed for the DB part
    res = await save_memory_core(entities=entities, observations=observations)
    assert "Saved" in res

    # Verify data is in DB despite API failure
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'ResilientEntity'")
        row = await cursor.fetchone()
        assert row is not None
