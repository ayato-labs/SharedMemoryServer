import json

import pytest

from shared_memory import logic, thought_logic
from shared_memory.database import async_get_connection, init_db
from shared_memory.insights import InsightEngine


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db(force=True)


@pytest.mark.asyncio
async def test_full_lifecycle_system(mock_llm):
    """
    [System Test]
    Simulates a sequence of AI thoughts leading to complex memory saving
    and retrieval, then verifying via insights.
    """
    # 1. Start with a Thought (Lazy init triggered)
    print("Recording Thought process...")
    # Mock search hit for previous principle
    mock_llm.models.generate_content.return_value.text = json.dumps(
        {"conflict": False, "reason": "Aligned with architecture."}
    )

    await thought_logic.process_thought_core(
        thought="Designing mapping_audit table for traceability.duckdb.",
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id="session_lifecycle_test",
    )

    # 2. Save Memory based on thought result
    print("Saving derived knowledge...")
    await logic.save_memory_core(
        entities=[
            {
                "name": "mapping_audit",
                "entity_type": "table",
                "description": "Audit table",
            }
        ],
        agent_id="test_lifecycle_agent",
    )

    # 3. Check Insights
    print("Checking Insights...")
    metrics = await InsightEngine.get_summary_metrics()
    assert metrics["facts"]["stored_entities"] >= 1

    report = InsightEngine.generate_report_markdown(metrics)
    assert "SharedMemory Fact Report" in report

    # 4. Verify Final Consistency
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM entities WHERE name='mapping_audit'")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "mapping_audit"
