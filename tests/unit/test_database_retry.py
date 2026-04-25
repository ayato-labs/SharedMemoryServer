import asyncio
import pytest
import aiosqlite
from shared_memory.database import async_get_connection, retry_on_db_lock, init_db

@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_on_db_lock_logic():
    """
    Directly tests the retry_on_db_lock decorator by simulating a lock.
    """
    call_count = 0
    
    # Passing arguments to the decorator
    @retry_on_db_lock(max_retries=3, initial_delay=0.1)
    async def mock_db_op():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise aiosqlite.OperationalError("database is locked")
        return "success"

    result = await mock_db_op()
    assert result == "success"
    assert call_count == 3

@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_on_db_lock_exhaustion():
    """
    Tests that it eventually gives up after max_retries.
    """
    call_count = 0
    
    from shared_memory.exceptions import DatabaseLockedError
    
    @retry_on_db_lock(max_retries=2, initial_delay=0.1)
    async def failing_db_op():
        nonlocal call_count
        call_count += 1
        raise aiosqlite.OperationalError("database is locked")

    with pytest.raises(DatabaseLockedError) as excinfo:
        await failing_db_op()
    
    assert "locked after 2 attempts" in str(excinfo.value)
    assert call_count == 2

@pytest.mark.asyncio
@pytest.mark.unit
async def test_real_db_lock_contention():
    """
    Simulates real lock contention by holding a connection in a transaction.
    """
    await init_db()
    
    # Connection 1: Hold a lock using a separate connection
    # Note: Our singleton connection architecture might make this tricky if they share the same object.
    # We'll use a direct aiosqlite connect to ensure it's a DIFFERENT connection object.
    from shared_memory.utils import get_db_path
    db_path = get_db_path()
    
    conn1 = await aiosqlite.connect(db_path)
    await conn1.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    @retry_on_db_lock(max_retries=5, initial_delay=0.1)
    async def try_write():
        async with await async_get_connection() as conn:
            await conn.execute("INSERT INTO entities (name, entity_type) VALUES ('LockTest', 'test')")
            await conn.commit()
        return True

    # Start the write attempt in background
    write_task = asyncio.create_task(try_write())
    
    # Wait a bit to ensure it hits the lock and starts retrying
    await asyncio.sleep(0.3)
    
    # Release the lock from connection 1
    await conn1.rollback()
    await conn1.close()
    
    # Now the write_task should succeed on its next retry
    success = await write_task
    assert success is True
    
    # Verify the write happened
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM entities WHERE name='LockTest'")
        row = await cursor.fetchone()
        assert row[0] == 'LockTest'
