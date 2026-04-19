import sqlite3
from unittest.mock import patch

import pytest

from shared_memory.database import DatabaseLockedError, async_get_connection
from shared_memory.logic import save_memory_core


@pytest.mark.asyncio
async def test_integration_handles_locked_db(mock_llm):
    """
    Integration test: Verify that the system handles a locked database
    gracefully during a save operation.
    """
    # Force a locking error when executing SQL
    with patch(
        "aiosqlite.Connection.execute", side_effect=sqlite3.OperationalError("database is locked")
    ):
        entities = [{"name": "LockedEntity", "description": "Crash test"}]

        # We expect the DatabaseLockedError to propagate or be handled depending on retry decorator
        # Actually, save_memory_core uses retry_on_db_lock internally (via database.py helpers)
        # So it should raise DatabaseLockedError after retries.
        with pytest.raises(DatabaseLockedError):
            await save_memory_core(entities=entities)


@pytest.mark.asyncio
async def test_integration_handles_malformed_input():
    """Integration test: Verify that massive or malformed input doesn't crash the server."""
    # Massive entity list
    entities = [{"name": f"Entity_{i}", "description": "X" * 1000} for i in range(500)]

    # This should handle high volume gracefully
    res = await save_memory_core(entities=entities)
    assert "Saved 500 entities" in res


@pytest.mark.asyncio
async def test_integration_path_traversal_prevention():
    """Integration test: Strict check for illegal path traversal in bank files."""
    from shared_memory.logic import save_memory_core

    # Attempting to write outside bank directory
    bank_files = [{"filename": "../unauthorized.txt", "content": "I should not be here"}]

    # The sanitize_filename should catch this
    await save_memory_core(bank_files=bank_files)

    # It should have been sanitized to 'unauthorized.txt' or similar, not '../'
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT filename FROM bank_files")
        filenames = [row[0] for row in await cursor.fetchall()]
        assert "../unauthorized.txt" not in filenames
        # It should be 'unauthorized.txt'
        assert "unauthorized.txt" in filenames
