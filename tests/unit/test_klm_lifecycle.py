import pytest

from shared_memory import logic
from shared_memory.database import async_get_connection, init_db


@pytest.mark.asyncio
async def test_klm_status_toggle_and_search_filtering():
    """
    Unit Test: Verify that toggling knowledge status correctly affects search visibility.
    """
    await init_db(force=True)

    # 1. Save dummy knowledge
    entities = [{"name": "HiddenEntity", "description": "This should be hidden"}]
    await logic.save_memory_core(entities=entities)

    # 2. Verify it is initially searchable
    res = await logic.read_memory_core(query="HiddenEntity")
    assert any(e["name"] == "HiddenEntity" for e in res["graph"]["entities"])

    # 3. Deactivate it
    await logic.manage_knowledge_activation_core(["HiddenEntity"], "inactive")

    # 4. Verify it is no longer searchable
    res_hidden = await logic.read_memory_core(query="HiddenEntity")
    assert not any(e["name"] == "HiddenEntity" for e in res_hidden["graph"]["entities"])

    # 5. Verify it is in the inactive list
    inactive_list = await logic.list_inactive_knowledge_core()
    assert any(e["name"] == "HiddenEntity" for e in inactive_list["entities"])

    # 6. Reactivate it
    await logic.manage_knowledge_activation_core(["HiddenEntity"], "active")
    res_active = await logic.read_memory_core(query="HiddenEntity")
    assert any(e["name"] == "HiddenEntity" for e in res_active["graph"]["entities"])


@pytest.mark.asyncio
async def test_cascading_deactivation():
    """
    Unit Test: Verify that deactivating an entity also deactivates its relations and observations.
    """
    await init_db(force=True)

    entities = [{"name": "Parent", "description": "Parent entity"}]
    relations = [{"subject": "Parent", "object": "Target", "predicate": "links_to"}]
    observations = [{"entity_name": "Parent", "content": "Fact about parent"}]

    # Need to ensure Target exists for FK
    await logic.save_memory_core(entities=[{"name": "Target", "description": "T"}])
    await logic.save_memory_core(entities=entities, relations=relations, observations=observations)

    # Deactivate Parent
    await logic.manage_knowledge_activation_core(["Parent"], "inactive")

    async with await async_get_connection() as conn:
        # Check relations
        cursor = await conn.execute("SELECT status FROM relations WHERE subject = 'Parent'")
        row = await cursor.fetchone()
        assert row[0] == "inactive"

        # Check observations
        cursor = await conn.execute("SELECT status FROM observations WHERE entity_name = 'Parent'")
        row = await cursor.fetchone()
        assert row[0] == "inactive"
