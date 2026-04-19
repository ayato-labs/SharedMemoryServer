from unittest.mock import patch

import pytest

from shared_memory import lifecycle, logic
from shared_memory.database import init_db
from shared_memory.exceptions import DatabaseLockedError


@pytest.mark.asyncio
async def test_klm_db_lock_resilience(mock_llm):
    """
    Robustness Test: Verify that manage_knowledge_activation handles DB locks using the retry decorator.
    """
    await init_db(force=True)
    await logic.save_memory_core(entities=[{"name": "LockedItem", "description": "X"}])

    # Simulate DB lock on the first call
    call_count = 0
    original_execute = None

    async def side_effect(sql, *args, **kwargs):
        nonlocal call_count
        if "UPDATE" in sql and call_count < 2:
            call_count += 1
            raise DatabaseLockedError("Database is locked")
        return await original_execute(sql, *args, **kwargs)

    from shared_memory.database import async_get_connection

    async with await async_get_connection() as conn:
        original_execute = conn.execute
        with patch.object(conn, "execute", side_effect=side_effect):
            # This should trigger retries and eventually succeed
            result = await lifecycle.manage_knowledge_activation_logic(["LockedItem"], "inactive")
            assert "Success" in result
            assert call_count >= 2


@pytest.mark.asyncio
async def test_klm_nonexistent_ids_resilience(mock_llm):
    """
    Robustness Test: Verify that deactivating non-existent IDs does not crash and returns 0 changes.
    """
    await init_db(force=True)
    result = await lifecycle.manage_knowledge_activation_logic(["Ghost_ID_999"], "inactive")
    assert "Updated 0 items" in result


@pytest.mark.asyncio
async def test_klm_bulk_stress(mock_llm):
    """
    Robustness Test: Verify that updating 100+ items at once works correctly.
    """
    await init_db(force=True)
    count = 100
    entities = [{"name": f"E_{i}", "description": str(i)} for i in range(count)]
    await logic.save_memory_core(entities=entities)

    ids = [f"E_{i}" for i in range(count)]
    result = await lifecycle.manage_knowledge_activation_logic(ids, "inactive")

    assert f"Updated {count}" in result

    # Verify a sample
    res = await logic.read_memory_core(query="E_50")
    assert not any(e["name"] == "E_50" for e in res["graph"]["entities"])
