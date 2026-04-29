from unittest.mock import patch

import pytest

from shared_memory.core import graph
from shared_memory.infra.database import async_get_connection, init_db


@pytest.mark.asyncio
async def test_add_entities_to_graph():
    """Verify adding entities to the graph."""
    await init_db(force=True)
    entities = [
        {"name": "E1", "entity_type": "T1", "description": "D1"},
        {"name": "E2", "entity_type": "T2", "description": "D2"},
    ]

    async with await async_get_connection() as conn:
        await graph.save_entities(entities, "test_agent", conn)

    # Verify via search
    results = await graph.get_graph_data(query="E1")
    assert "entities" in results
    assert len(results["entities"]) >= 1
    assert results["entities"][0]["name"] == "E1"


@pytest.mark.asyncio
async def test_check_conflict_isolated(fake_llm_client):
    """Verify conflict checking using FakeGeminiClient."""
    await init_db(force=True)

    # Set up existing entity
    async with await async_get_connection() as conn:
        await graph.save_entities(
            [{"name": "Static", "description": "Old info"}], "test_agent", conn
        )

    # Mocking both sync and async client getters
    with patch("shared_memory.core.graph.get_gemini_client", return_value=fake_llm_client):
        # Case 1: No conflict (FakeClient default)
        conflicts = await graph.check_conflict(["Static"], ["New info"])
        assert conflicts[0][0] is False

        # Case 2: Force conflict via FakeClient
        print(f"DEBUG: fake_llm_client.models type: {type(fake_llm_client.models)}")
        fake_llm_client.models.set_response(
            method_name="generate_content", text='{"conflict": true, "reason": "Already exists"}'
        )
        conflicts = await graph.check_conflict(["Static"], ["Old info"])
        assert conflicts[0][0] is True
        assert conflicts[0][1] == "Already exists"


@pytest.mark.asyncio
async def test_add_relations():
    """Verify adding relations between entities."""
    await init_db(force=True)
    async with await async_get_connection() as conn:
        await graph.save_entities([{"name": "A"}, {"name": "B"}], "test_agent", conn)

        relations = [{"subject": "A", "object": "B", "predicate": "links_to"}]
        await graph.save_relations(relations, "test_agent", conn)

        async with conn.execute("SELECT subject, object FROM relations") as cursor:
            rows = await cursor.fetchall()
            assert len(rows) >= 1
            assert rows[0]["subject"] == "A"
            assert rows[0]["object"] == "B"
