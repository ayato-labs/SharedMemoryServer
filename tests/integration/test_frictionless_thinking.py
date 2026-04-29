import json
from unittest.mock import MagicMock

import pytest

from shared_memory.database import async_get_connection
from shared_memory.thought_logic import process_thought_core


@pytest.mark.asyncio
async def test_frictionless_accretion_and_salvage(mock_llm):
    """
    Tests the 'Frictionless Memory' cycle:
    1. Thought A contains a new fact -> System distills it into DB.
    2. Thought B in a new session asks about it -> System salvages it from DB.
    """
    from shared_memory.ai_control import AIRateLimiter

    AIRateLimiter.set_min_interval(0)

    # --- SETUP MOCK BEHAVIOR ---

    def llm_side_effect(model, contents, config=None):
        prompt = contents
        # Create a mock response object
        response = MagicMock()

        if "SINGLE THOUGHT" in prompt:
            # Incremental Distillation Prompt
            # Return a JSON containing the PHX-2026 code name
            response.text = json.dumps(
                {
                    "entities": [
                        {
                            "name": "Project Phoenix",
                            "entity_type": "project",
                            "description": "A top-secret research initiative.",
                        }
                    ],
                    "relations": [],
                    "observations": [
                        {"entity_name": "Project Phoenix", "content": "Code name is PHX-2026."}
                    ],
                }
            )
        elif "Knowledge Re-ranking Engine" in prompt:
            # Salvage Re-ranking Prompt
            # Return indices. Assuming the first item (0) is our target.
            response.text = json.dumps([0])
        else:
            # Default empty response
            response.text = json.dumps({"entities": [], "relations": [], "observations": []})

        return response

    # Assign side effect to the async mock
    mock_llm.aio.models.generate_content.side_effect = llm_side_effect

    # --- STEP 1: LEARNING PHASE (Session A) ---

    session_a = "session_learning"
    thought_a = "Our secret research Project Phoenix has the code name PHX-2026."

    await process_thought_core(
        thought=thought_a,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id=session_a,
    )

    # Wait for the background distillation task to complete
    from shared_memory.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    # Check if the entity reached the DB
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM entities WHERE name = 'Project Phoenix'")
        found_in_db = await cursor.fetchone() is not None

    assert found_in_db, "Entity 'Project Phoenix' was never distilled into the database."

    # Verify observation
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name = 'Project Phoenix'"
        )
        row = await cursor.fetchone()
        assert row is not None, "Observation for 'Project Phoenix' missing."
        assert "PHX-2026" in row[0], f"Expected PHX-2026 in observation, got: {row[0]}"

    # --- STEP 2: RECALL PHASE (Session B) ---

    session_b = "session_recall"
    thought_b = "I need to recall the code name for Project Phoenix."

    # This call should trigger salvage_related_knowledge
    result_b = await process_thought_core(
        thought=thought_b,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id=session_b,
    )

    # Verify that 'related_knowledge' in the output contains our learning from Session A
    related = result_b.get("related_knowledge", [])

    # DEBUG: Print related knowledge if check fails
    found_fact = False
    for item in related:
        # Check both the ID (entity name) and the content (observation/description)
        if "Project Phoenix" in str(item.get("id")) or "PHX-2026" in str(item.get("content")):
            found_fact = True
            break

    msg = (
        f"Frictionless recall failed.\nSalvaged items: "
        f"{json.dumps(related, indent=2)}\nThought B: {thought_b}"
    )
    assert found_fact, msg


@pytest.mark.asyncio
async def test_thought_privacy_masking(mock_llm):
    """Verifies that sensitive data in thoughts is masked before storage."""
    session_id = "privacy_test"
    sensitive_thought = (
        "My secret key is sk-1234567890abcdef1234567890 and my email is test@example.com"
    )

    await process_thought_core(
        thought=sensitive_thought,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id=session_id,
    )

    from shared_memory.database import async_get_thoughts_connection

    async with await async_get_thoughts_connection() as conn:
        cursor = await conn.execute(
            "SELECT thought FROM thought_history WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        saved_thought = row[0]

        assert "sk-1234567890abcdef1234567890" not in saved_thought
        assert "test@example.com" not in saved_thought
        assert "[API_KEY_MASKED]" in saved_thought
        assert "[EMAIL_MASKED]" in saved_thought
