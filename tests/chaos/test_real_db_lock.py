import asyncio
import os
import sqlite3

import pytest

from shared_memory import logic


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_real_sqlite_lock_recovery():
    """
    HARSH TEST: Verify that the system recovers from a REAL SQLite database lock.
    We use a synchronous sqlite3 connection to hold an EXCLUSIVE lock.
    """
    db_path = os.environ.get("MEMORY_DB_PATH")
    
    # 1. Open a raw connection and start a transaction to lock the DB
    sync_conn = sqlite3.connect(db_path)
    sync_conn.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    # 2. Attempt a write operation via SharedMemoryServer
    write_task = asyncio.create_task(
        logic.save_memory_core(
            entities=[{"name": "LockTest", "description": "Testing lock recovery"}]
        )
    )
    
    await asyncio.sleep(0.5)
    assert not write_task.done()
    
    # 3. Release the lock
    sync_conn.rollback()
    sync_conn.close()
    
    # 4. The write task should now complete successfully
    result = await asyncio.wait_for(write_task, timeout=10.0)
    assert "Saved" in result

@pytest.mark.asyncio
@pytest.mark.chaos
async def test_lock_timeout_failure():
    """
    HARSH TEST: Verify that it eventually fails if the lock is never released.
    """
    db_path = os.environ.get("MEMORY_DB_PATH")
    
    # 1. Lock the DB permanently for the duration of the test
    sync_conn = sqlite3.connect(db_path)
    sync_conn.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    # 2. Attempt a write
    result = await logic.save_memory_core(
        entities=[{"name": "FailTest", "description": "Testing lock exhaustion"}]
    )
    
    assert "error" in result.lower()
    assert "locked" in result.lower()
    
    sync_conn.rollback()
    sync_conn.close()
