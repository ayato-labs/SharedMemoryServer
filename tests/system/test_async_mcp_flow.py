import json

import pytest

from shared_memory.api import server


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_memory_async_system_flow(fake_llm):
    """
    E2E System Test: Verify that save_memory returns immediately
    and the background task eventually completes.
    """
    entities = [{"name": "SystemEntity", "entity_type": "concept", "description": "A test entity"}]
    observations = [{"entity_name": "SystemEntity", "content": "System test fact"}]

    # Call the tool with both entity and observation
    response = await server.save_memory(entities=entities, observations=observations)

    assert "Saved" in response

    # Wait for the background task to complete
    from shared_memory.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    from shared_memory.core.search import search_memory_logic

    # Retry a few times if not immediately visible (SQLite isolation/indexing)
    max_retries = 5
    res = {}
    for attempt in range(max_retries):
        res = await search_memory_logic("SystemEntity")
        obs_list = res.get("observations", [])
        if any("System test fact" in r["content"] for r in obs_list):
            break
        if attempt < max_retries - 1:
            import asyncio
            await asyncio.sleep(0.5)
    else:
        pytest.fail(
            f"Asynchronous save did not complete in time or entity not searchable. Found: {res}"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_full_thought_to_knowledge_loop(fake_llm):
    """
    Tests the complete loop: Thought -> Distillation (Background) -> Persistence.
    """
    from shared_memory.core import thought_logic
    from shared_memory.core.search import search_memory_logic

    session_id = "system_test_session"
    # The thought should be clear so the distiller extracts an entity and observation
    thought = "SharedMemoryServer is a powerful tool. It supports asynchronous saving."

    # Setup Fake LLM response for distillation
    fake_llm.models.set_response(
        "generate_content",
        json.dumps(
            {
                "entities": [
                    {
                        "name": "SharedMemoryServer",
                        "entity_type": "software",
                        "description": "Memory server",
                    }
                ],
                "relations": [],
                "observations": [
                    {"entity_name": "SharedMemoryServer", "content": "Supports asynchronous saving"}
                ],
                "bank_files": [],
            }
        ),
    )

    # 1. Process a thought (this triggers incremental distillation in background)
    await thought_logic.process_thought_core(
        thought=thought,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id=session_id,
    )

    # 2. The distillation is a background task. Wait for it.
    from shared_memory.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    results = await search_memory_logic("SharedMemoryServer")
    obs_list = results.get("observations", [])
    if not any("asynchronous saving" in r["content"].lower() for r in obs_list):
        pytest.fail("Knowledge was not distilled and saved in time.")
