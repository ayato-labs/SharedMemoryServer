import pytest

from shared_memory.logic import (
    get_value_report_core,
    read_memory_core,
    save_memory_core,
    synthesize_entity,
)


@pytest.mark.asyncio
async def test_complete_user_workflow(mock_llm):
    """
    Simulates a complete user scenario.
    """
    agent = "workflow_agent"

    # Setup mock responses for synthesis
    mock_llm.models.set_response(
        "generate_content",
        "Synthesized summary: This entity is a test node with multiple observations.",
    )

    # 1. Build context
    await save_memory_core(
        entities=[{"name": "ProjectX", "description": "A top-secret project"}], agent_id=agent
    )

    await save_memory_core(
        observations=[
            {"entity_name": "ProjectX", "content": "Phase 1 is complete."},
            {"entity_name": "ProjectX", "content": "Budget approved for Phase 2."},
        ],
        agent_id=agent,
    )

    # 2. Retrieve synthesis
    summary = await synthesize_entity("ProjectX")
    assert "Synthesized summary" in summary

    # 3. Check search effectiveness
    search_res = await read_memory_core("ProjectX")
    assert search_res["graph"]["entities"][0]["name"] == "ProjectX"
    assert len(search_res["graph"]["observations"]) >= 2

    # 4. Generate report
    report = await get_value_report_core(format_type="markdown")
    assert "# SharedMemory Fact Report" in report
    assert "熟成" in report


@pytest.mark.asyncio
async def test_error_resilience_malformed_input(mock_llm):
    """System level test for resilience against bad inputs."""
    # Extremely long string
    huge_string = "A" * 10000

    result = await save_memory_core(
        entities=[{"name": huge_string, "description": "Massive name"}], agent_id="test_agent"
    )
    assert "Saved" in result

    # Missing required keys in list
    result2 = await save_memory_core(entities=[{"not_a_name": "oops"}], agent_id="test_agent")
    assert "Saved 0 entities" in result2
