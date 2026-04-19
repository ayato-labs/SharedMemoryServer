import pytest
import json
from shared_memory import logic, thought_logic
from shared_memory.database import init_db, async_get_connection
from shared_memory.insights import InsightEngine

@pytest.fixture(autouse=True)
async def setup_env():
    await init_db(force=True)
    await thought_logic.init_thoughts_db(force=True)

@pytest.mark.asyncio
async def test_ff_lifecycle_full_system(mock_llm):
    """
    System Test: Full lifecycle mimicking the 'Financial Figures' dogfooding session.
    1. Initialize Project context.
    2. Save Architectural Principles.
    3. Execute Sequential Thinking and record reasoning.
    4. Generate Insight Report and verify traceability.
    """
    # 1. Save Principals
    print("Saving Architecture...")
    res1 = await logic.save_memory_core(
        entities=[{
            "name": "Traceability-First-Design",
            "entity_type": "Principle",
            "description": "Hardened audit trail principle."
        }],
        agent_id="architect_v1"
    )
    assert "Saved 1 entities" in res1

    # 2. Record Thinking (Reasoning persistence)
    print("Recording Thought process...")
    # Mock search hit for previous principle
    mock_llm.models.generate_content.return_value.text = json.dumps({
        "conflict": False, 
        "reason": "Aligned with architecture."
    })
    
    await thought_logic.process_thought_core(
        thought="Designing mapping_audit table for traceability.duckdb.",
        thought_number=1, total_thoughts=1, next_thought_needed=False,
        session_id="ff_design_001"
    )

    # 3. Verify Memory retrieval
    print("Verifying Retrieval...")
    res_mem = await logic.read_memory_core(query="traceability")
    assert "Traceability-First-Design" in str(res_mem)

    # 4. Generate Insight Report
    print("Checking Insights...")
    metrics = await InsightEngine.get_summary_metrics()
    assert metrics["facts"]["stored_entities"] >= 1
    
    report = InsightEngine.generate_report_markdown(metrics)
    assert "SharedMemory Fact Report" in report

    # 5. Check Audit Logs (Final Verification of Traceability)
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT meta_data FROM audit_logs")
        logs = await cursor.fetchall()
        assert len(logs) >= 1
        meta = json.loads(logs[0][0])
        assert "timestamp" in meta
