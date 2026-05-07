import asyncio

import aiosqlite
import pytest

from shared_memory.infra.database import retry_on_db_lock

pytestmark = pytest.mark.chaos


@pytest.mark.asyncio
async def test_db_lock_retry_chaos():
    """
    Chaos Test: Force a DB lock and verify that retry_on_db_lock handles it.
    """
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "chaos.db")

        # 1. Open a connection and start a transaction without committing
        conn1 = await aiosqlite.connect(db_path)
        await conn1.execute("CREATE TABLE IF NOT EXISTS chaos (id INTEGER PRIMARY KEY)")
        await conn1.execute("BEGIN IMMEDIATE TRANSACTION")
        await conn1.execute("INSERT INTO chaos VALUES (1)")
        # conn1 holds the lock

        @retry_on_db_lock(max_retries=3, initial_delay=0.1)
        async def locked_write():
            async with aiosqlite.connect(db_path) as conn2:
                await conn2.execute("INSERT INTO chaos VALUES (2)")
                await conn2.commit()

        # 2. Run the locked write in a task
        write_task = asyncio.create_task(locked_write())

        # 3. Wait a bit, then commit conn1 to release lock
        await asyncio.sleep(0.2)
        await conn1.commit()
        await conn1.close()

        # 4. Verify that locked_write eventually succeeded
        await write_task

        async with aiosqlite.connect(db_path) as conn3:
            cursor = await conn3.execute("SELECT COUNT(*) FROM chaos")
            count = (await cursor.fetchone())[0]
            assert count == 2


@pytest.mark.asyncio
async def test_ai_outage_graceful_degradation(monkeypatch, db_conn):
    """
    Chaos Test: Simulate AI failure and verify fallback.
    """
    from shared_memory.core.search import perform_search

    # Setup data
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description) "
        "VALUES ('FallbackItem', 'test', 'Keyword match only')"
    )
    await db_conn.commit()

    # Mock AI to fail
    async def failing_embed(q):
        raise Exception("AI Service Down")

    monkeypatch.setattr("shared_memory.core.search.compute_embedding", failing_embed)

    # Perform Search - Should fall back to keyword search
    graph_data, _ = await perform_search("FallbackItem")

    assert any(e["name"] == "FallbackItem" for e in graph_data["entities"])
