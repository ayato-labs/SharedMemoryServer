import json
import pytest
from datetime import datetime
from shared_memory.graph import check_conflict, save_observations
from shared_memory.database import async_get_connection, init_db

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db(force=True)

@pytest.mark.asyncio
async def test_check_conflict_detected_unit(mock_gemini_globally):
    """Unit test: Verify conflict detection yields 'True' when Gemini detects conflict."""
    # 1. Setup: Pre-existing observation
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO entities (name, description) VALUES (?, ?)",
            ("Apple", "A fruit")
        )
        await conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            ("Apple", "Apples are sweet.", "user1")
        )
        await conn.commit()

    # 2. Setup: Program Fake LLM to report conflict
    mock_gemini_globally.models.set_response(
        "generate_content", 
        '{"conflict": true, "reason": "Apples are not salty."}'
    )

    # 3. Test
    is_conflict, reason = await check_conflict("Apple", "Apples are salty.", "user2")
    
    assert is_conflict is True
    assert "not salty" in reason

    # 4. Verify DB persistence of conflict
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT reason FROM conflicts WHERE entity_name = ?", ("Apple",))
        row = await cursor.fetchone()
        assert row is not None
        assert "not salty" in row[0]

@pytest.mark.asyncio
async def test_audit_log_metadata_persistence_unit(mock_gemini_globally):
    """Unit test: Verify that saving an observation creates a detailed audit log with meta_data."""
    # 1. Setup entities
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name) VALUES (?)", ("ProjectX",))
        await conn.commit()

    # 2. Program Fake LLM (No conflict)
    mock_gemini_globally.models.set_response(
        "generate_content", 
        '{"conflict": false, "reason": "Consistent"}'
    )

    # 3. Action
    async with await async_get_connection() as conn:
        await save_observations([{"entity_name": "ProjectX", "content": "Started today"}], "agent_007", conn)
        await conn.commit()

    # 4. Verification
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT meta_data FROM audit_logs WHERE content_id = ? AND table_name = 'observations' ORDER BY timestamp DESC", 
            ("ProjectX",)
        )
        row = await cursor.fetchone()
        assert row is not None
        meta = json.loads(row[0])
        assert meta["agent_context"] == "development_trace"
