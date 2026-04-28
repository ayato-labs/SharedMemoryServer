import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared_memory import logic


@pytest.mark.asyncio
async def test_save_memory_pipeline_with_quota_rotation(mock_llm):
    """
    Tests that the save_memory pipeline handles 429 errors by rotating models.
    """
    from shared_memory.database import async_get_connection
    # Pre-insert to trigger LLM check (otherwise it skips if no existing knowledge)
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            ("QuotaEntity", "Initial fact", "setup")
        )
        await conn.commit()

    # 1. Setup mock_llm to fail once then succeed
    call_count = 0
    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 RESOURCE_EXHAUSTED")
        return MagicMock(text=json.dumps({"conflict": False, "reason": "Recovered"}))

    mock_llm.aio.models.generate_content.side_effect = side_effect
    observations = [{"entity_name": "QuotaEntity", "content": "Testing rotation"}]
    
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("asyncio.sleep", AsyncMock())
        result = await logic.save_memory_core(
            observations=observations, agent_id="integration_test"
        )
    
    assert "Saved 1 observations" in result
    assert call_count >= 2

@pytest.mark.asyncio
async def test_save_memory_partial_failure_robustness(mock_llm):
    """
    Tests how the system handles a partial failure during the parallel conflict check.
    """
    from shared_memory.database import async_get_connection
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO observations (entity_name, content) VALUES (?, ?)", ("GoodEntity", "init")
        )
        await conn.execute(
            "INSERT INTO observations (entity_name, content) VALUES (?, ?)", ("BadEntity", "init")
        )
        await conn.commit()

    async def side_effect(model, contents, **kwargs):
        if "BadEntity" in contents or "BadEntity" in str(kwargs.get("contents", "")):
            raise Exception("500 Internal Server Error for this entity")
        # Response for GoodEntity
        return MagicMock(text=json.dumps([{"conflict": False, "reason": "OK"}]))

    mock_llm.aio.models.generate_content.side_effect = side_effect
    observations = [
        {"entity_name": "GoodEntity", "content": "Good fact"},
        {"entity_name": "BadEntity", "content": "Bad fact"},
    ]
    
    result = await logic.save_memory_core(observations=observations, agent_id="integration_test")
    
    # Now that logic.py is fixed, it should ONLY save the one that didn't error.
    assert "Saved 1 observations" in result
