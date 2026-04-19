import os
import threading
import time

import aiosqlite
import pytest

from shared_memory import database, logic
from shared_memory.utils import get_db_path


@pytest.mark.asyncio
async def test_chaos_database_lock_retry(mock_llm):
    """
    Chaos Test: Artificially lock the database from another thread and
    ensure the 'retry_on_db_lock' decorator handles it gracefully.
    """
    db_path = get_db_path()

    def lock_database():
        # Standard sqlite3 library (sync) to hold a long-term lock
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute("BEGIN EXCLUSIVE")
        time.sleep(2)  # Hold lock for 2 seconds
        conn.rollback()
        conn.close()

    # 1. Start the blocker thread
    locker = threading.Thread(target=lock_database)
    locker.start()
    time.sleep(0.5)  # Ensure the blocker gets the lock first

    # 2. Action
    # The retry decorator (initial_delay=0.1) should catch up after the lock
    # is released.
    res = await logic.save_memory_core(
        entities=[{"name": "ChaosEntity", "description": "Resilience test"}]
    )

    assert "Saved 1 entities" in res
    locker.join()


@pytest.mark.asyncio
async def test_chaos_database_permission_error(mock_llm):
    """Chaos Test: Simulate a DatabaseError when file permissions are revoked."""
    db_path = get_db_path()

    # Close singleton to release handle before chmod
    await database.close_all_connections()

    # Make read-only
    os.chmod(db_path, 0o444)

    try:
        # Saving should fail
        # aiosqlite or our wrapper will throw DatabaseError
        from shared_memory.exceptions import DatabaseError

        with pytest.raises(DatabaseError):
            await logic.save_memory_core(entities=[{"name": "NoSave"}])
    finally:
        # Restore permissions and re-open to avoid breaking teardown
        os.chmod(db_path, 0o666)
        # database._DB_INITIALIZED being True might prevent re-init,
        # but conftest will force it.


@pytest.mark.asyncio
async def test_chaos_corrupted_metadata_parsing(mock_llm):
    """
    Chaos Test: Manually inject invalid JSON into meta_data and ensure the
    server doesn't crash when trying to read from it.
    """
    # 1. Setup Data
    await logic.save_memory_core(entities=[{"name": "BrokenMeta", "description": "Crash test"}])

    # 2. Corrupt metadata manually
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "UPDATE knowledge_metadata SET access_count = -1, "
            "stability = 'NOT_A_REAL_JSON' WHERE content_id = 'BrokenMeta'"
        )
        await conn.commit()

    # 3. Action: Read memory (which might involve audit logs or statistics)
    # The system should handle the parsing error gracefully.
    # Note: Currently read_memory_core doesn't read audit_logs directly,
    # but some future logic might. This test ensures we are robust.
    results = await logic.read_memory_core(query="BrokenMeta")
    assert "BrokenMeta" in str(results)
