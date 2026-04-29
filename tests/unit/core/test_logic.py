from unittest.mock import patch

import pytest

from shared_memory.core import logic
from shared_memory.infra.database import init_db


@pytest.mark.asyncio
async def test_normalize_entities():
    """Verify entity normalization logic."""
    raw = ["Simple String", {"name": "Dict Object", "description": "Desc"}, {"name": "Partial"}]
    normalized = logic.normalize_entities(raw)
    assert len(normalized) == 3
    assert normalized[0]["name"] == "Simple String"
    assert normalized[1]["description"] == "Desc"
    assert normalized[2]["entity_type"] == "concept"  # Default


@pytest.mark.asyncio
async def test_save_memory_core_isolated(fake_llm_client):
    """Verify save_memory_core orchestrates components correctly without MagicMock."""
    await init_db(force=True)

    # Mocking compute_embeddings_bulk to avoid real calls inside logic
    # and using fake_llm_client for conflict checks.
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        with patch("shared_memory.core.graph.get_gemini_client", return_value=fake_llm_client):
            entities = [{"name": "Cortex", "description": "Core Logic"}]

            result = await logic.save_memory_core(entities=entities)

            assert "Saved 1 entities" in result

            # Check if saved in DB
            from shared_memory.core.graph import get_graph_data

            saved = await get_graph_data(query="Cortex")
            assert "entities" in saved
            assert len(saved["entities"]) >= 1
            assert saved["entities"][0]["name"] == "Cortex"


@pytest.mark.asyncio
async def test_save_memory_core_with_conflict(fake_llm_client):
    """Verify behavior when conflict is detected."""
    await init_db(force=True)

    # Pre-save
    await logic.save_memory_core(entities=[{"name": "ConflictNode", "description": "Existing"}])

    # Force conflict in FakeClient
    print(f"DEBUG LOGIC: fake_llm_client.models type: {type(fake_llm_client.models)}")
    fake_llm_client.models.set_response(
        "generate_content", '{"conflict": true, "reason": "Already exists"}'
    )

    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        with patch("shared_memory.core.graph.get_gemini_client", return_value=fake_llm_client):
            # We need observations to trigger conflict check
            entities = [{"name": "ConflictNode", "description": "Duplicate"}]
            obs = [{"entity_name": "ConflictNode", "content": "I already exist"}]
            result = await logic.save_memory_core(entities=entities, observations=obs)

            # Entities report 0 saved if conflict (current implementation doesn't return
            # CONFLICTS message for entities)
            assert "Saved 0 entities" in result
            assert "CONFLICTS DETECTED" in result
            assert "Saved 0 observations" in result
