import pytest

from shared_memory import logic
from shared_memory.database import init_db


@pytest.mark.asyncio
async def test_klm_agent_decision_workflow_system(mock_llm):
    """
    System Test: High-level user story for decision retirement.
    1. Agent records 'Legacy Decision'.
    2. Agent records 'New Decision'.
    3. Agent 'retires' Legacy Decision by deactivating it.
    4. System confirms only 'New Decision' is present in active context.
    """
    await init_db(force=True)
    agent_id = "architect_agent"

    # 1. Record Legacy Decision
    await logic.save_memory_core(
        entities=[{"name": "Decision_V1", "description": "Use Legacy Port 80"}], agent_id=agent_id
    )

    # 2. Record New Decision
    await logic.save_memory_core(
        entities=[{"name": "Decision_V2", "description": "Use New Port 443"}], agent_id=agent_id
    )

    # 3. Verify both exist
    res = await logic.read_memory_core()
    assert len(res["graph"]["entities"]) == 2

    # 4. Agent retires V1
    await logic.manage_knowledge_activation_core(["Decision_V1"], "inactive")

    # 5. Verify search only finds V2
    # Semantic search fallback (keyword) for 'Decision'
    res_context = await logic.read_memory_core(query="Decision")
    entities = res_context["graph"]["entities"]

    assert any(e["name"] == "Decision_V2" for e in entities)
    assert not any(e["name"] == "Decision_V1" for e in entities)

    # 6. Verify agent can still see V1 if they check inactive list
    inactive = await logic.list_inactive_knowledge_core()
    assert any(e["name"] == "Decision_V1" for e in inactive["entities"])
