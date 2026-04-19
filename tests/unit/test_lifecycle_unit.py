import pytest

from shared_memory import lifecycle, logic
from shared_memory.database import async_get_connection, init_db


@pytest.mark.asyncio
@pytest.mark.no_global_mock
async def test_manage_knowledge_activation_unit(mock_gemini_client):
    """
    Unit Test: Verify logic of manage_knowledge_activation_logic.
    Uses FakeGeminiClient for determinism.
    """
    await init_db(force=True)

    # Setup
    entities = [{"name": "E1", "entity_type": "T1", "description": "D1"}]
    await logic.save_memory_core(entities=entities)

    # 1. Deactivate
    result = await lifecycle.manage_knowledge_activation_logic(["E1"], "inactive")
    assert "Updated" in result

    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'E1'")
        row = await cursor.fetchone()
        assert row["status"] == "inactive"

    # 2. Re-activate
    await lifecycle.manage_knowledge_activation_logic(["E1"], "active")
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'E1'")
        row = await cursor.fetchone()
        assert row["status"] == "active"


@pytest.mark.asyncio
@pytest.mark.no_global_mock
async def test_list_inactive_knowledge_unit(mock_gemini_client):
    """
    Unit Test: Verify list_inactive_knowledge_logic returns structured inactive data.
    """
    await init_db(force=True)

    # Setup: 1 active, 1 inactive
    await logic.save_memory_core(entities=[{"name": "A1", "description": "Active"}])
    await logic.save_memory_core(entities=[{"name": "I1", "description": "Inactive"}])
    await lifecycle.manage_knowledge_activation_logic(["I1"], "inactive")

    results = await lifecycle.list_inactive_knowledge_logic()

    assert len(results["entities"]) == 1
    assert results["entities"][0]["name"] == "I1"
    assert results["entities"][0]["status"] == "inactive"
    # Ensure active ones aren't listed
    assert not any(e["name"] == "A1" for e in results["entities"])


@pytest.mark.asyncio
@pytest.mark.no_global_mock
async def test_run_knowledge_gc_unit(mock_gemini_client):
    """
    Unit Test: Verify GC logic for deactivating stale knowledge.
    """
    await init_db(force=True)

    # 1. Create a "Stale" item (Old access, Low importance)
    await logic.save_memory_core(entities=[{"name": "StaleEntity", "description": "Old news"}])

    async with await async_get_connection() as conn:
        # Manually create the metadata record (since save_memory_core doesn't do it)
        # Using julianday directly ensures SQLite compatibility
        await conn.execute(
            "INSERT OR REPLACE INTO knowledge_metadata "
            "(content_id, last_accessed, importance_score) "
            "VALUES ('StaleEntity', datetime('now', '-200 days'), 0.05)"
        )
        await conn.commit()

    # 2. Run GC
    result = await lifecycle.run_knowledge_gc_logic(age_days=100)
    assert "GC Complete" in result

    # 3. Verify status is now inactive
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'StaleEntity'")
        row = await cursor.fetchone()
        assert row["status"] == "inactive"


@pytest.mark.asyncio
@pytest.mark.no_global_mock
async def test_invalid_status_rejection_unit(mock_gemini_client):
    """
    Unit Test: Verify that invalid status strings are rejected.
    """
    result = await lifecycle.manage_knowledge_activation_logic(["Any"], "deleted")
    assert "Error: Invalid status" in result
