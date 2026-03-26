import pytest
from unittest.mock import patch, MagicMock
from shared_memory.logic import save_memory_core
from shared_memory.exceptions import SharedMemoryError, DatabaseLockedError
from shared_memory.database import get_connection, init_db


@pytest.fixture(autouse=True)
def setup_db(mock_gemini):
    init_db()


@pytest.mark.asyncio
async def test_save_memory_atomicity(mock_gemini):
    """
    Verify that if any part of save_memory fails (e.g. bank file write),
    the entire transaction is rolled back in the database.
    """
    entities = [{"name": "ShouldNotBeSaved", "description": "Crash testing"}]
    bank_files = {"crash.md": "Trigger a crash"}

    # 1. Mock save_bank_files to raise an exception
    with patch(
        "shared_memory.bank.save_bank_files", side_effect=Exception("Disk Full")
    ):
        with pytest.raises(SharedMemoryError) as excinfo:
            await save_memory_core(entities=entities, bank_files=bank_files)
        assert "Disk Full" in str(excinfo.value)

    # 2. Verify that 'ShouldNotBeSaved' is NOT in the database
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM entities WHERE name = 'ShouldNotBeSaved'"
    ).fetchone()
    assert row is None
    conn.close()


@pytest.mark.asyncio
async def test_llm_json_malformed_resilience(mock_gemini):
    """
    Verify that if the LLM returns non-JSON garbage, the system doesn't crash
    and handles it gracefully in conflict detection.
    """
    mock_gemini.models.generate_content.return_value = MagicMock(
        text="This is not JSON!"
    )

    entities = [{"name": "RobustEntity", "description": "Testing parser"}]
    observations = [
        {"entity_name": "RobustEntity", "content": "This might trigger conflict logic"}
    ]

    # We expect it to log error and continue (or return no conflict)
    # Depending on how parser is written.
    res = await save_memory_core(entities=entities, observations=observations)
    assert "Saved" in res

    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM observations WHERE entity_name = 'RobustEntity'"
    ).fetchone()
    assert row is not None
    conn.close()


@pytest.mark.asyncio
async def test_db_lock_retry_simulation(mock_gemini):
    """
    Verify that the retry_on_db_lock decorator logic is triggered.
    """
    from shared_memory.database import retry_on_db_lock
    import sqlite3

    mock_op = MagicMock()
    # Fail 2 times then succeed
    mock_op.side_effect = [
        sqlite3.OperationalError("database is locked"),
        sqlite3.OperationalError("database is locked"),
        "Success",
    ]

    @retry_on_db_lock(max_retries=5, initial_delay=0.01)
    def test_func():
        return mock_op()

    res = test_func()
    assert res == "Success"
    assert mock_op.call_count == 3

@pytest.mark.asyncio
async def test_db_lock_failure_raises_custom_exception(mock_gemini):
    """
    Verify that if retries are exhausted, DatabaseLockedError is raised.
    """
    from shared_memory.database import retry_on_db_lock
    import sqlite3

    mock_op = MagicMock()
    mock_op.side_effect = sqlite3.OperationalError("database is locked")

    @retry_on_db_lock(max_retries=2, initial_delay=0.01)
    def fail_func():
        return mock_op()

    with pytest.raises(DatabaseLockedError):
        fail_func()
    assert mock_op.call_count == 2


@pytest.mark.asyncio
async def test_api_failure_resilience(mock_gemini):
    """
    Verify that if the Gemini API is completely down (raises exception),
    the system still saves the core data and doesn't crash the entire flow.
    """
    # Simulate a complete API failure (e.g. Connection Error)
    mock_gemini.models.embed_content.side_effect = Exception("API Connection Failed")
    mock_gemini.models.generate_content.side_effect = Exception("API Connection Failed")

    entities = [{"name": "ResilientEntity", "entity_type": "Testing"}]
    observations = [{"entity_name": "ResilientEntity", "content": "Critical info"}]

    # The save should still succeed for the DB part, even if embeddings/distillation fail
    res = await save_memory_core(entities=entities, observations=observations)
    assert "Saved" in res

    # Verify data is in DB despite API failure
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM entities WHERE name = 'ResilientEntity'"
    ).fetchone()
    assert row is not None
    conn.close()
