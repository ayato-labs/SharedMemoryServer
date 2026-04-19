import pytest
import asyncio
import aiosqlite
from unittest.mock import patch
from shared_memory import logic, database
from shared_memory.exceptions import DatabaseLockedError

@pytest.mark.chaos
@pytest.mark.asyncio
async def test_db_lock_retry_chaos():
    """Chaos: Verify that retry_on_db_lock recovers from transient 'database is locked' errors."""
    mock_call_count = 0
    
    @database.retry_on_db_lock(max_retries=3, initial_delay=0.01)
    async def flaky_function():
        nonlocal mock_call_count
        mock_call_count += 1
        if mock_call_count < 3:
            raise aiosqlite.OperationalError("database is locked")
        return "Success"
    
    result = await flaky_function()
    assert result == "Success"
    assert mock_call_count == 3

@pytest.mark.chaos
@pytest.mark.asyncio
async def test_db_lock_exhaustion_chaos():
    """Chaos: Verify that persistent locks eventually raise DatabaseLockedError."""
    
    @database.retry_on_db_lock(max_retries=2, initial_delay=0.01)
    async def perma_locked():
        raise aiosqlite.OperationalError("database is locked")
    
    with pytest.raises(DatabaseLockedError):
        await perma_locked()

@pytest.mark.chaos
@pytest.mark.asyncio
async def test_malformed_llm_json_chaos(fake_llm):
    """Chaos: Verify that malformed JSON from LLM doesn't crash the conflict logic."""
    from shared_memory.database import init_db
    await init_db(force=True)
    
    fake_llm.models.set_response("generate_content", "This is NOT json { [")
    
    # This should be handled gracefully (conflicts detection skipped)
    res = await logic.save_memory_core(
        observations=[{"entity_name": "E1", "content": "C1"}]
    )
    
    assert "Saved 1 observations" in res
    assert "CONFLICTS DETECTED" not in res

@pytest.mark.chaos
@pytest.mark.asyncio
async def test_database_connection_failure_chaos():
    """Chaos: Verify behavior when the DB file is not a database."""
    from shared_memory.database import init_db, get_db_path, close_all_connections
    import sqlite3
    
    db_path = get_db_path()
    
    # CRITICAL: Close all existing connections to the file before overwriting it
    # Otherwise, some OSs might keep a handle to the old file or WAL
    await close_all_connections()
    
    # Write garbage to the DB file
    with open(db_path, "wb") as f:
        f.write(b"NOT A SQLITE DATABASE")
    
    # init_db(force=True) should fail because SELECT 1 check will fail
    with pytest.raises(Exception):
        await init_db(force=True)
