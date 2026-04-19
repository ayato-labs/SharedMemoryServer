import asyncio
import sqlite3

import pytest

from shared_memory.database import DatabaseLockedError, async_get_connection, retry_on_db_lock


@pytest.mark.asyncio
async def test_database_singleton_connection():
    """Verify that multiple calls to async_get_connection return the same underlying singleton."""
    async with await async_get_connection() as conn1:
        async with await async_get_connection() as conn2:
            # Check if they point to the same global connection
            assert conn1 == conn2


@pytest.mark.asyncio
async def test_retry_on_db_lock_success():
    """Verify that the retry decorator handles temporary locks successfully."""
    call_count = 0

    @retry_on_db_lock(max_retries=3, initial_delay=0.01)
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise sqlite3.OperationalError("database is locked")
        return "success"

    result = await flaky_function()
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_on_db_lock_exhaustion():
    """Verify that the retry decorator eventually raises DatabaseLockedError."""

    @retry_on_db_lock(max_retries=2, initial_delay=0.01)
    async def locking_function():
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(DatabaseLockedError):
        await locking_function()


@pytest.mark.asyncio
async def test_concurrent_access_stress():
    """
    Stress test: Concurrent database access.
    Multiple async tasks performing operations simultaneously.
    """
    from shared_memory.database import update_access

    tasks = [update_access(f"concurrent_item_{i}") for i in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for any exceptions
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Got {len(errors)} errors during stress test: {errors}"
