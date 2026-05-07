import asyncio
import json

import pytest

from shared_memory.api import server


@pytest.mark.asyncio
async def test_e2e_researcher_workflow(mock_llm):
    """
    SYSTEM TEST: Simulate a researcher's full workflow using MCP tools.
    1. Save background research.
    2. Start a reasoning session.
    3. Retrieve gathered knowledge.
    4. Finish session and verify distilled insights.
    """
    # 1. Researcher saves an observation
    res1 = await server.save_memory(
        observations=[
            {"entity_name": "Antigravity", "content": "Antigravity is an agentic AI assistant."}
        ],
        agent_id="researcher_01",
    )
    assert "Saved" in res1

    # Ensure background save is finished before proceeding
    from shared_memory.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    # 2. Researcher starts thinking
    session_id = "research_task_42"
    res2_raw = await server.sequential_thinking(
        thought="I need to understand how Antigravity manages memory.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_id,
    )
    res2 = json.loads(res2_raw)
    assert "thoughtNumber" in res2

    # 3. Researcher reads memory during thinking
    # (The system should return the observation saved in step 1)
    res3_raw = await server.read_memory(query="Antigravity")
    res3 = json.loads(res3_raw)
    assert any("AI assistant" in obs["content"] for obs in res3["graph"]["observations"])

    # 4. Researcher finishes thinking
    # Mock distillation result for the final step
    distilled_knowledge = {
        "entities": [
            {
                "name": "Memory Management",
                "entity_type": "Mechanism",
                "description": "How AI stores state",
            }
        ],
        "relations": [
            {
                "source": "Antigravity",
                "target": "Memory Management",
                "relation_type": "uses",
                "justification": "E2E Test",
            }
        ],
        "observations": [],
    }
    mock_llm.models.set_response("generate_content", json.dumps(distilled_knowledge))

    await server.sequential_thinking(
        thought="Antigravity uses a Graph DB and a Markdown Bank for memory.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id=session_id,
    )

    # Wait for background distillation
    from shared_memory.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    # 5. Verify the new knowledge is searchable
    # Distillation results are saved via save_memory_core in background
    await wait_for_background_tasks(timeout=5.0)

    # Use entity name which is definitely indexed
    res5_raw = await server.read_memory(query="Memory Management")
    res5 = json.loads(res5_raw)

    entities_found = [e["name"] for e in res5["graph"]["entities"]]
    assert "Memory Management" in entities_found

    # 6. Final verification - read insights
    # Wait for all background tasks (including potentially nested ones)
    for _ in range(5):
        await wait_for_background_tasks(timeout=1.0)
        res_insights_raw = await server.get_insights(format="json")
        res_insights = json.loads(res_insights_raw)
        if res_insights["facts"]["stored_entities"] >= 1:
            break
        await asyncio.sleep(0.5)

    assert res_insights["facts"]["stored_entities"] >= 1
