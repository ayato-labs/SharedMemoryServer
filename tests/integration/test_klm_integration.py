import pytest

from shared_memory import logic
from shared_memory.database import init_db


@pytest.mark.asyncio
async def test_klm_search_integration_flow(mock_llm):
    """
    Integration Test: Verify Save -> Deactivate -> Search flow.
    Ensures that the search module correctly respects the status set by the lifecycle module.
    """
    await init_db(force=True)

    # 1. Save knowledge
    entities = [{"name": "FeatureA", "description": "Experimental feature"}]
    observations = [{"entity_name": "FeatureA", "content": "Initial research complete."}]
    await logic.save_memory_core(entities=entities, observations=observations)

    # 2. Verify visibility
    res = await logic.read_memory_core(query="FeatureA")
    assert any(e["name"] == "FeatureA" for e in res["graph"]["entities"])
    assert len(res["graph"]["observations"]) > 0

    # 3. Deactivate the feature
    await logic.manage_knowledge_activation_core(["FeatureA"], "inactive")

    # 4. Verify invisibility
    res_hidden = await logic.read_memory_core(query="FeatureA")
    assert not any(e["name"] == "FeatureA" for e in res_hidden["graph"]["entities"])
    assert len(res_hidden["graph"]["observations"]) == 0

    # 5. Verify it's in the inactive list
    inactive = await logic.list_inactive_knowledge_core()
    assert any(e["name"] == "FeatureA" for e in inactive["entities"])


@pytest.mark.asyncio
async def test_klm_cascading_visibility_integration(mock_llm):
    """
    Integration Test: Verify that deactivating an entity hides its relations.
    """
    await init_db(force=True)

    # Setup Entity and Relation
    await logic.save_memory_core(
        entities=[{"name": "Alpha", "description": "A"}, {"name": "Beta", "description": "B"}]
    )
    await logic.save_memory_core(
        relations=[{"subject": "Alpha", "object": "Beta", "predicate": "leads_to"}]
    )

    # Verify relation is visible
    res = await logic.read_memory_core()  # Get all
    assert any(r["subject"] == "Alpha" for r in res["graph"]["relations"])

    # Deactivate Alpha
    await logic.manage_knowledge_activation_core(["Alpha"], "inactive")

    # Verify relation is now hidden because one of its endpoints is inactive
    res_hidden = await logic.read_memory_core()
    assert not any(r["subject"] == "Alpha" for r in res_hidden["graph"]["relations"])
