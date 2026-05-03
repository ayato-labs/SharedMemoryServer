import json

import pytest

from shared_memory.api.server import (
    admin_run_knowledge_gc,
    get_insights,
    read_memory,
    save_memory,
)
from shared_memory.infra.database import init_db

pytestmark = pytest.mark.system

@pytest.mark.asyncio
async def test_full_lifecycle_flow(db_conn, monkeypatch):
    """
    System Test: Full lifecycle from creation to deactivation.
    1. Save Memory (Entity + Tags)
    2. Read Memory (Search & Access Update)
    3. Check Insights (Maturity/Hit Rate)
    4. Run GC (Deactivation)
    """
    # Initialize DB tables
    await init_db()

    # Mock AI for save_memory
    from tests.unit.fake_client import FakeGeminiClient
    fake_client = FakeGeminiClient()
    fake_client.models.set_response("generate_content", '["#new_feature"]')
    monkeypatch.setattr("shared_memory.infra.embeddings.get_gemini_client", lambda: fake_client)
    monkeypatch.setattr("shared_memory.core.graph.get_gemini_client", lambda: fake_client)
    
    # 1. Save
    await save_memory(
        entities=[{
            "name": "LifecycleTarget", 
            "entity_type": "feature", 
            "description": "System test content"
        }]
    )
    
    # 2. Read (Update heat)
    res_str = await read_memory("LifecycleTarget")
    res = json.loads(res_str)
    # read_memory returns {"graph": ..., "bank": ...}
    assert len(res["graph"]["entities"]) > 0
    
    # 3. Get Insights
    insights = await get_insights(format="json")
    insights_data = json.loads(insights)
    assert "facts" in insights_data
    assert insights_data["facts"]["stored_entities"] >= 1
    
    # 4. GC (Triggering for an item that is NOT stale yet)
    gc_res = await admin_run_knowledge_gc(age_days=180, dry_run=False)
    assert "No stale knowledge" in gc_res # Should not be stale yet
    
    # 5. Manually force staleness and run GC
    await db_conn.execute(
        "UPDATE knowledge_metadata "
        "SET last_accessed = '2020-01-01T00:00:00Z' "
        "WHERE content_id = 'LifecycleTarget'"
    )
    await db_conn.commit()
    
    gc_res_stale = await admin_run_knowledge_gc(age_days=180, dry_run=False)
    assert "GC Complete" in gc_res_stale
    
    # 6. Verify deactivation
    res_final_str = await read_memory("LifecycleTarget")
    res_final = json.loads(res_final_str)
    assert len(res_final["graph"]["entities"]) == 0 # Should be inactive now
