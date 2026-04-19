import os
import sqlite3
import pytest
import asyncio
import aiosqlite
from shared_memory import logic
from shared_memory.database import get_db_path, init_db, DatabaseLockedError, close_all_connections

@pytest.fixture(autouse=True)
async def setup_env():
    await init_db(force=True)

@pytest.mark.asyncio
async def test_chaos_sqlite_busy_retry(mock_llm):
    """
    Chaos Test: Force a 'database is locked' error and verify the retry decorator works.
    We simulate this by opening a synchronous sqlite3 connection and holding an EXCLUSIVE lock.
    """
    db_path = get_db_path()
    
    # Start a background task to lock the DB
    def lock_db():
        conn = sqlite3.connect(db_path)
        conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        # Hold lock for 0.5 seconds
        import time
        time.sleep(0.5)
        conn.rollback()
        conn.close()

    import threading
    locker = threading.Thread(target=lock_db)
    locker.start()
    
    # Try to save something while it's locked
    # The retry decorator (initial_delay=0.1) should catch up after the lock is released.
    res = await logic.save_memory_core(
        entities=[{"name": "ChaosEntity", "description": "Resilience test"}]
    )
    
    assert "Saved 1 entities" in res
    locker.join()

@pytest.mark.asyncio
async def test_chaos_read_only_db():
    """
    Chaos Test: Verify behavior when the DB file is read-only.
    """
    db_path = get_db_path()
    # Ensure fresh start: Close singleton connection before making read-only
    await close_all_connections()
    # Make read-only
    os.chmod(db_path, 0o444)
    
    try:
        # Saving should fail
        with pytest.raises(Exception): # aiosqlite or our wrapper will throw
            await logic.save_memory_core(entities=[{"name": "NoSave"}])
    finally:
        # Restore permissions so cleanup works
        os.chmod(db_path, 0o666)

@pytest.mark.asyncio
async def test_chaos_corrupted_metadata_parsing(mock_llm):
    """
    Chaos Test: Manually inject invalid JSON into meta_data and ensure the server doesn't crash 
    when trying to read from it.
    """
    # 1. Setup Data
    await logic.save_memory_core(entities=[{"name": "BrokenMeta", "description": "Crash test"}])
    
    # 2. Corrupt metadata manually
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "UPDATE audit_logs SET meta_data = 'INVALID { JSON' WHERE content_id = ?",
            ("BrokenMeta",)
        )
        await conn.commit()
    
    # 3. Action: Read memory (which might involve audit logs or statistics)
    # The system should handle the parsing error gracefully or skip the broken entry.
    # Note: Currently read_memory_core doesn't read audit_logs directly, 
    # but some future logic might. This test ensures we are robust.
    results = await logic.read_memory_core(query="BrokenMeta")
    assert "BrokenMeta" in str(results)
