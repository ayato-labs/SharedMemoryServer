import os

import aiosqlite
import pytest

from ripen.common.exceptions import DatabaseLockedError
from ripen.infra.database import (
    AsyncSQLiteConnection,
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
    async with await AsyncSQLiteConnection(db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            rows = await cursor.fetchall()
            tables = [row["name"] for row in rows]
            assert "entities" in tables
            assert "relations" in tables
            assert "observations" in tables


@pytest.mark.asyncio
async def test_async_sqlite_connection_singleton():
    """Verify that AsyncSQLiteConnection returns a valid connection wrapper
    and maintains singleton."""
    db_path = get_db_path()
    conn_wrapper = await AsyncSQLiteConnection(db_path)
    async with conn_wrapper as conn1:
        assert isinstance(conn1, aiosqlite.Connection)

        conn_wrapper2 = await AsyncSQLiteConnection(db_path)
        async with conn_wrapper2 as conn2:
            assert conn1 is conn2  # Should be the same underlying singleton connection


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


@pytest.mark.asyncio
async def test_database_write_and_read():
    """Verify that we can write and read data using the connection."""
    await init_db(force=True)
    db_path = get_db_path()
    async with await AsyncSQLiteConnection(db_path) as db:
        await db.execute(
            "INSERT INTO entities (name, description) VALUES ('TestNode', 'Test desc')"
        )
        await db.commit()

        async with db.execute(
            "SELECT description FROM entities WHERE name='TestNode'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["description"] == "Test desc"
