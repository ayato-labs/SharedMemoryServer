import asyncio
import json

import pytest

from ripen.api import server


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
    from ripen.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    from ripen.core.search import search_memory_logic

    # Retry a few times if not immediately visible (SQLite isolation/indexing)
    max_retries = 5
    res = {}
    for attempt in range(max_retries):
        res = await search_memory_logic("SystemEntity")
        obs_list = res.get("observations", [])
        if any("System test fact" in r["content"] for r in obs_list):
            break
        if attempt < max_retries - 1:
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
    from ripen.core import thought_logic
    from ripen.core.search import search_memory_logic

    session_id = "system_test_session"
    # The thought should be clear so the distiller extracts an entity and observation
    thought = "Ripen is a powerful tool. It supports asynchronous saving."

    # Setup Fake LLM response for distillation
    fake_llm.models.set_response(
        "generate_content",
        json.dumps(
            {
                "entities": [
                    {
                        "name": "Ripen",
                        "entity_type": "software",
                        "description": "Memory server",
                    }
                ],
                "relations": [],
                "observations": [
                    {"entity_name": "Ripen", "content": "Supports asynchronous saving"}
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
    from ripen.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks(timeout=5.0)

    # Use a retry loop for search as embeddings might take a moment to be searchable
    # (though they should be ready if save_memory_core was awaited)
    found = False
    for _ in range(3):
        results = await search_memory_logic("Ripen")
        obs_list = results.get("observations", [])
        if any("asynchronous saving" in r["content"].lower() for r in obs_list):
            found = True
            break
        await asyncio.sleep(1.0)

    if not found:
        # Fallback check directly in DB
        from ripen.infra.database import async_get_connection

        async with await async_get_connection() as conn:
            cursor = await conn.execute(
                "SELECT content FROM observations WHERE entity_name='Ripen'"
            )
            rows = await cursor.fetchall()
            print(f"DEBUG: Observations in DB: {[r[0] for r in rows]}")
            if any("asynchronous saving" in r[0].lower() for r in rows):
                found = True

    assert found, "Knowledge was not distilled and saved in time."
