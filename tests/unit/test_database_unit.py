import pytest

from shared_memory.database import async_get_connection, init_db, update_access


@pytest.mark.asyncio
async def test_init_db_schema():
    """Unit test for init_db and schema sanity check."""
    await init_db()
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in await cursor.fetchall()]
        assert "entities" in tables
        assert "relations" in tables
        assert "observations" in tables
        assert "audit_logs" in tables
        assert "embedding_cache" in tables


@pytest.mark.asyncio
async def test_update_access_unit():
    """Unit test for update_access function logic."""
    await init_db()
    content_id = "test_item_1"

    # First access
    await update_access(content_id)

    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = ?",
            (content_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1

        # Second access (stability should increase)
        initial_stability = row[1]
        await update_access(content_id)

        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = ?",
            (content_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == 2
        assert row[1] > initial_stability
