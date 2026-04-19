import pytest

from shared_memory import lifecycle, logic, search
from shared_memory.database import init_db


@pytest.mark.system
@pytest.mark.asyncio
async def test_intelligence_provenance_lifecycle_scenario(fake_llm):
    """
    System: Comprehensive lifecycle of knowledge for 'Project Aether'.
    Workflow: Ingestion -> Cross-Agent Discovery -> Aging -> GC -> Archival Discovery.
    """
    await init_db(force=True)

    # 1. Ingestion of core knowledge
    await logic.save_memory_core(
        entities=[{"name": "Project Aether", "description": "Next-gen AI safety framework"}],
        agent_id="ArchitectAgent",
    )

    # 2. Cross-agent discovery
    # Another agent searches for the project
    results = await search.search_memory_logic("Aether")
    assert any(e["name"] == "Project Aether" for e in results["entities"])

    # 3. Knowledge Aging & GC
    # (Simulating time passage by manually deactivating -
    # standard GC logic is unit tested elsewhere)
    await lifecycle.manage_knowledge_activation_logic(["Project Aether"], "inactive")

    # 4. Inactive Search (Discovery from graveyard)
    # Standard search should NOT return it
    active_search = await search.search_memory_logic("Aether")
    assert not any(e["name"] == "Project Aether" for e in active_search["entities"])

    # Graveyard search SHOULD return it
    inactive_list = await lifecycle.list_inactive_knowledge_logic()
    assert any(e["name"] == "Project Aether" for e in inactive_list["entities"])

    # 5. Full restoration
    await lifecycle.manage_knowledge_activation_logic(["Project Aether"], "active")
    restored_search = await search.search_memory_logic("Aether")
    assert any(e["name"] == "Project Aether" for e in restored_search["entities"])
