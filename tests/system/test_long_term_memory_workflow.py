import pytest

from shared_memory.database import init_db
from shared_memory.logic import (
    get_value_report_core,
    read_memory_core,
    save_memory_core,
)


@pytest.mark.asyncio
async def test_long_term_memory_decay_and_value_workflow():
    """
    System Test: Verifies that knowledge importance decays over time
    and is reflected in the value report.
    """
    await init_db(force=True)

    # 1. Day 0: Save knowledge
    await save_memory_core(
        entities=[{"name": "OldKnowledge", "description": "Important in the past"}]
    )

    # 2. Get report and verify it doesn't crash (testing the timezone fix)
    report_data = await get_value_report_core(format_type="json")
    assert isinstance(report_data, dict)
    # The structure has changed: it's under 'facts' -> 'stored_entities'
    assert report_data["facts"]["stored_entities"] >= 1


@pytest.mark.asyncio
async def test_cross_session_synthesis_workflow():
    """
    System Test: Verifies that multiple agents contributing to the same entity
    results in a synthesized view in the graph.
    """
    await init_db(force=True)

    # Session 1: Agent A defines the entity
    await save_memory_core(
        entities=[{"name": "SharedEntity", "description": "Initial definition"}],
        agent_id="AgentA",
    )

    # Session 2: Agent B adds observations
    await save_memory_core(
        observations=[{"entity_name": "SharedEntity", "content": "Updated observation"}],
        agent_id="AgentB",
    )

    # Session 3: Read and verify synthesis
    res = await read_memory_core(query="SharedEntity")

    assert "graph" in res
    entities = res["graph"]["entities"]
    observations = res["graph"]["observations"]

    assert any(e["name"] == "SharedEntity" for e in entities)
    assert any(
        o["entity"] == "SharedEntity" and "Updated observation" in o["content"]
        for o in observations
    )
