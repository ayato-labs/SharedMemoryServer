import json

import pytest

from shared_memory import logic
from shared_memory.database import async_get_connection, init_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db(force=True)


@pytest.mark.asyncio
async def test_audit_trail_flow_integration(mock_llm):
    """
    Integration Test: Verify that complex save operations correctly log
    detailed audit trails with conflict metadata.
    Uses mock_llm (MagicMock) to simulate specific complex scenarios.
    """
    # 1. Action: Save memory with metadata
    entities = [{"name": "Kernel-v2", "entity_type": "component", "description": "Core kernel"}]
    observations = [{"entity_name": "Kernel-v2", "content": "Initialized with high memory"}]

    # 0. Setup: Pre-existing knowledge to trigger conflict check
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name) VALUES (?)", ("Kernel-v2",))
        await conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            ("Kernel-v2", "Previous state", "user1"),
        )
        await conn.commit()

    # Simulate a conflict detected by the mock
    mock_llm.models.generate_content.return_value.text = json.dumps(
        {"conflict": True, "reason": "Memory conflict with v1"}
    )

    await logic.save_memory_core(entities=entities, observations=observations, agent_id="admin_bot")

    # 2. Verification: Check audit logs for observations specifically
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT action, meta_data FROM audit_logs WHERE content_id = ? "
            "AND table_name = 'observations' ORDER BY timestamp DESC",
            ("Kernel-v2",),
        )
        logs = await cursor.fetchall()

        assert len(logs) >= 1
        meta = json.loads(logs[0][1])
        assert meta["conflict_info"]["reason"] == "Memory conflict with v1"


@pytest.mark.asyncio
async def test_save_memory_transactional_integrity_integration(mock_llm):
    """
    Integration test: Verify that if one part of save_memory fails,
    we still maintain an audit trail or handle it gracefully.
    """
    # Trigger an error during observation saving (malformed payload handled in loop)
    entities = [{"name": "SolidEntity", "description": "Should be saved"}]
    malformed_observations = [{"entity": "NonExistent", "content": "Should fail"}]

    # We want to check if entities are still saved if observations fail,
    # OR if the whole transaction reverts (depending on current implementation).
    # Current save_memory_core uses individual blocks for entities/relations.

    res = await logic.save_memory_core(entities=entities, observations=malformed_observations)

    assert "Saved 1 entities" in res
    assert "Errors: 1" in res  # Because non-existent entity for observation
