import json
from unittest.mock import patch

import pytest

from shared_memory.common.tasks import wait_for_background_tasks
from shared_memory.core.thought_logic import process_thought_core
from shared_memory.infra.database import async_get_connection


@pytest.mark.asyncio
async def test_frictionless_accretion_and_salvage(mock_llm):
    """
    Tests the 'Frictionless Memory' cycle:
    1. Thought A contains a new fact -> System distills it into DB.
    2. Thought B in a new session asks about it -> System salvages it from DB.
    """
    from shared_memory.api import server

    await server.ensure_initialized()

    # --- SETUP MOCK BEHAVIOR ---
    # Use a side effect that returns different things based on content
    async def llm_side_effect(prompt, system_instruction=None):
        if "SINGLE THOUGHT" in prompt or "Analyze the complete reasoning history" in prompt:
            return json.dumps(
                {
                    "entities": [
                        {
                            "name": "Project Phoenix",
                            "entity_type": "project",
                            "description": "Top secret",
                        }
                    ],
                    "relations": [],
                    "observations": [
                        {"entity_name": "Project Phoenix", "content": "Code name is PHX-2026."}
                    ],
                }
            )
        if "Knowledge Re-ranking Engine" in prompt:
            return json.dumps([0])
        return json.dumps({"entities": [], "relations": [], "observations": []})

    # Patch the provider instead of just the model to be sure
    with patch(
        "shared_memory.infra.llm.GeminiProvider.generate_content", side_effect=llm_side_effect
    ):
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
        await wait_for_background_tasks(timeout=5.0)

        # Check if the entity reached the DB
        async with await async_get_connection() as conn:
            cursor = await conn.execute("SELECT name FROM entities WHERE name = 'Project Phoenix'")
            row = await cursor.fetchone()
            assert row is not None, (
                "Entity 'Project Phoenix' was never distilled into the database."
            )

        # --- STEP 2: SALVAGE PHASE (Session B) ---
        # A new session asks a related question
        session_b = "session_asking"
        thought_b = "What is the code name of Project Phoenix?"

        result = await process_thought_core(
            thought=thought_b,
            thought_number=1,
            total_thoughts=1,
            next_thought_needed=True,
            session_id=session_b,
        )

        # Verify that Project Phoenix knowledge was salvaged
        related = result.get("related_knowledge", [])
        related_texts = [str(k) for k in related]
        assert any("PHX-2026" in t for t in related_texts), (
            f"Salvage failed. Related: {related_texts}"
        )


@pytest.mark.asyncio
async def test_thought_privacy_masking():
    """
    Tests that sensitive data in thoughts is masked before being logged or processed.
    """
    # ... existing test logic is fine ...
    from shared_memory.common.utils import mask_sensitive_data

    thought = "My API key is AIzaSyD-dummy-key and my email is test@example.com"
    masked = mask_sensitive_data(thought)
    assert "[GOOGLE_API_KEY_MASKED]" in masked
    assert "[EMAIL_MASKED]" in masked
