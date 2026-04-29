import os

import aiosqlite
import pytest

from shared_memory.common.exceptions import DatabaseLockedError
from shared_memory.infra.database import (
    async_get_connection,
    get_db_path,
    init_db,
    retry_on_db_lock,
)


@pytest.mark.asyncio
async def test_init_db_creates_file():
    """Verify that init_db creates the database file and tables."""
    # Use force=True to ensure fresh init within the test env
    await init_db(force=True)
    db_path = get_db_path()
    assert os.path.exists(db_path)

    # Check if tables exist
    async with await async_get_connection() as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            rows = await cursor.fetchall()
            tables = [row["name"] for row in rows]
            assert "entities" in tables
            assert "relations" in tables
            assert "observations" in tables


@pytest.mark.asyncio
async def test_async_get_connection_singleton():
    """Verify that async_get_connection returns a valid connection wrapper."""
    conn_wrapper = await async_get_connection()
    # Need to enter context to set conn
    async with conn_wrapper as conn:
        assert isinstance(conn, aiosqlite.Connection)

    conn_wrapper2 = await async_get_connection()
    assert conn_wrapper is conn_wrapper2  # Should be same wrapper instance


@pytest.mark.asyncio
async def test_retry_on_db_lock_success():
    """Verify that retry_on_db_lock works for normal calls."""

    @retry_on_db_lock(max_retries=2)
    async def success_func():
        return "ok"

    result = await success_func()
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_on_db_lock_failure():
    """Verify that retry_on_db_lock eventually fails after retries."""
    call_count = 0

    @retry_on_db_lock(max_retries=2, initial_delay=0.01)
    async def fail_func():
        nonlocal call_count
        call_count += 1
        import aiosqlite

        raise aiosqlite.OperationalError("database is locked")

    # The code raises DatabaseLockedError after max_retries
    with pytest.raises(DatabaseLockedError):
        await fail_func()

    # max_retries=2 means 2 attempts (Attempt 1, Attempt 2 raises)
    assert call_count == 2
