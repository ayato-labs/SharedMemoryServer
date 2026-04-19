import json

import pytest

from shared_memory.database import async_get_connection
from shared_memory.logic import save_memory_core


@pytest.mark.asyncio
async def test_save_memory_entities_unit(fake_llm):
    """
    Unit test for entity saving.
    Verifies that entities are stored in the database and audit logs are created.
    Uses FakeGeminiClient via fixture (non-mock).
    """
    entities = [
        {"name": "UnitEntity", "entity_type": "test", "description": "Unit test observation"}
    ]

    result = await save_memory_core(entities=entities, agent_id="test_agent")
    assert "Saved 1 entities" in result

    # Deep verify in DB
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT name, entity_type FROM entities WHERE name = ?", ("UnitEntity",)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[1] == "test"

        # Verify Audit Log
        cursor = await conn.execute(
            "SELECT action FROM audit_logs WHERE table_name = 'entities' AND content_id = ?",
            ("UnitEntity",),
        )
        audit = await cursor.fetchone()
        assert audit is not None
        assert audit[0] == "INSERT"


@pytest.mark.asyncio
async def test_save_memory_relations_unit(fake_llm):
    """Unit test for relation saving."""
    relations = [{"subject": "UnitA", "object": "UnitB", "predicate": "links_to"}]

    result = await save_memory_core(relations=relations, agent_id="test_agent")
    assert "Saved 1 relations" in result

    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM relations WHERE subject = ? AND object = ?", ("UnitA", "UnitB")
        )
        assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_save_memory_observations_unit(fake_llm):
    """Unit test for observation saving and conflict detection (via Fake LLM)."""
    # 1. First observation
    await save_memory_core(
        observations=[{"entity_name": "ConflictNode", "content": "The sky is blue"}],
        agent_id="agent_1",
    )

    # 2. Conflicting observation
    # FakeGeminiClient defaults to 'no conflict', so let's force a conflict response
    fake_llm.models.set_response(
        "generate_content", json.dumps({"conflict": True, "reason": "Scientific contradiction"})
    )

    result = await save_memory_core(
        observations=[{"entity_name": "ConflictNode", "content": "The sky is green"}],
        agent_id="agent_2",
    )

    # Check result - It should contain the conflict report
    assert "Saved 1 observations" in result
    assert "Scientific contradiction" in result

    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT count(*) FROM conflicts WHERE entity_name = ?", ("ConflictNode",)
        )
        count = (await cursor.fetchone())[0]
        assert count == 1


@pytest.mark.asyncio
async def test_save_memory_invalid_data_unit(fake_llm):
    """Unit test: Purposefully triggering various validation errors."""

    # Case A: Totally invalid entity (missing name)
    res = await save_memory_core(entities=[{"description": "No name"}])
    assert "Saved 0 entities" in res
    assert "Errors: 1" in res

    # Case B: Partially valid relations
    res = await save_memory_core(
        relations=[
            {"subject": "A", "object": "B", "predicate": "X"},
            {"subject": "A"},  # Missing object/predicate
        ]
    )
    assert "Saved 1 relations" in res
    assert "Errors: 1" in res
