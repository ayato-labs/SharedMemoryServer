import pytest

from shared_memory.database import async_get_connection
from shared_memory.logic import save_memory_core


@pytest.mark.asyncio
async def test_save_memory_integration_flow(mock_gemini):
    """
    Integration test for save_memory_core.
    Tests the interaction between embeddings, conflict detection, and DB persistence.
    Mocking Gemini is allowed here.
    """
    # 1. Execute full save flow
    entities = [{"name": "Integration Entity", "description": "Combined test"}]
    observations = [{"entity_name": "Integration Entity", "content": "Flow verification"}]

    result = await save_memory_core(
        entities=entities, observations=observations, agent_id="test_agent"
    )

    # 2. Verify results
    assert "Saved 1 entities" in result
    assert "Saved 1 observations" in result

    # 3. Check DB state
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT entity_type, description FROM entities WHERE name = ?",
            ("Integration Entity",),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "concept"
        assert row[1] == "Combined test"

        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name = ?",
            ("Integration Entity",),
        )
        obs_row = await cursor.fetchone()
        assert obs_row is not None
        assert obs_row[0] == "Flow verification"
