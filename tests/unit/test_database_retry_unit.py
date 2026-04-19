import asyncio
import pytest
import aiosqlite
from unittest.mock import AsyncMock
from shared_memory.database import retry_on_db_lock, DatabaseLockedError, DatabaseError

@pytest.mark.asyncio
async def test_retry_on_db_lock_success_unit():
    """Unit test: Verify that the decorator retries and eventually succeeds."""
    mock_func = AsyncMock()
    # 1st and 2nd attempt: Locked
    # 3rd attempt: Success
    mock_func.side_effect = [
        aiosqlite.OperationalError("database is locked"),
        aiosqlite.OperationalError("database is locked"),
        "success"
    ]

    # Patch sleep to speed up test
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(asyncio, "sleep", AsyncMock())
        
        decorated = retry_on_db_lock(max_retries=5, initial_delay=0.01)(mock_func)
        result = await decorated()
        
        assert result == "success"
        assert mock_func.call_count == 3

@pytest.mark.asyncio
async def test_retry_on_db_lock_failure_unit():
    """Unit test: Verify that the decorator eventually raises DatabaseLockedError."""
    mock_func = AsyncMock()
    mock_func.side_effect = aiosqlite.OperationalError("database is locked")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(asyncio, "sleep", AsyncMock())
        
        decorated = retry_on_db_lock(max_retries=3, initial_delay=0.01)(mock_func)
        
        with pytest.raises(DatabaseLockedError):
            await decorated()
        
        assert mock_func.call_count == 3

@pytest.mark.asyncio
async def test_retry_non_lock_error_unit():
    """Unit test: Verify that non-lock OperationalErrors are raised immediately."""
    mock_func = AsyncMock()
    mock_func.side_effect = aiosqlite.OperationalError("some other error")

    decorated = retry_on_db_lock(max_retries=5)(mock_func)
    
    with pytest.raises(aiosqlite.OperationalError):
        await decorated()
    
    assert mock_func.call_count == 1
