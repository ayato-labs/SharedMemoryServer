import pytest

from shared_memory.database import async_get_connection
from shared_memory.insights import InsightEngine


@pytest.mark.asyncio
async def test_get_summary_metrics_facts():
    """
    Unit test for get_summary_metrics.
    Verifies that the calculations for density, reuse, and hit rate are
    mathematically correct based on DB state.
    """
    async with await async_get_connection() as conn:
        # Prepare Fact Data: 2 entities, 1 relation, 1 search with 1 hit
        q = "INSERT INTO entities (name, entity_type, description) VALUES (?, ?, ?)"
        await conn.execute(q, ("A", "concept", "Desc A"))
        await conn.execute(q, ("B", "concept", "Desc B"))
        rq = "INSERT INTO relations (subject, object, predicate) VALUES (?, ?, ?)"
        await conn.execute(rq, ("A", "B", "connects"))

        # Metadata for reuse: A has 3 accesses, B has 1. Total = 4. Items = 2.
        mq = "INSERT INTO knowledge_metadata (content_id, access_count) VALUES (?, ?)"
        await conn.execute(mq, ("A", 3))
        await conn.execute(mq, ("B", 1))

        # Search stats: 2 total searches, 1 hit, 1 miss
        sq = "INSERT INTO search_stats (query, results_count) VALUES (?, ?)"
        await conn.execute(sq, ("query1", 5))
        await conn.execute(sq, ("query2", 0))
        await conn.commit()

    metrics = await InsightEngine.get_summary_metrics()
    f = metrics["facts"]
    i = metrics["efficiency_indicators"]

    # Assertions
    assert metrics["facts"]["stored_entities"] == 2
    assert metrics["facts"]["stored_relations"] == 1
    assert metrics["facts"]["search_hit_rate_percent"] == 50.0
    assert metrics["efficiency_indicators"]["reuse_multiplier"] == 2.0


@pytest.mark.asyncio
async def test_generate_report_markdown_unit():
    """
    Unit test for generate_report_markdown.
    Verifies that the markdown string contains all key fact sections.
    """
    metrics_data = {
        "timestamp": "2026-04-11T00:00:00",
        "facts": {
            "stored_entities": 10,
            "stored_relations": 5,
            "stored_bank_files": 2,
            "knowledge_graph_density_percent": 1.2,
            "total_read_operations": 50,
            "total_search_queries": 20,
            "search_hit_rate_percent": 75.0,
            "avg_thoughts_per_session": 4.5
        },
        "efficiency_indicators": {
            "reuse_multiplier": 5.0,
            "knowledge_availability_ratio": 80.0
        }
    }

    report = InsightEngine.generate_report_markdown(metrics_data)

    assert "# SharedMemory Fact Report" in report
    assert "## 1. 知識の蓄積状況" in report
    assert "## 2. 検索と利用の効率性" in report
    assert "## 3. 推論プロセスの観測" in report
    assert "10 items" in report
    assert "5.0x" in report
    assert "75.0%" in report
    assert "観測事実" in report

@pytest.mark.asyncio
async def test_generate_report_markdown():
    """
    Unit test for report generation.
    Ensures that the Markdown contains our key 'Fact' terms and no ROI speculation.
    """
    dummy_metrics = {
        "timestamp": "2026-04-11T10:00:00",
        "facts": {
            "stored_entities": 10,
            "stored_relations": 5,
            "stored_bank_files": 2,
            "knowledge_graph_density_percent": 12.5,
            "total_read_operations": 100,
            "total_search_queries": 20,
            "search_hit_rate_percent": 85.0,
            "avg_thoughts_per_session": 15.0
        },
        "efficiency_indicators": {
            "reuse_multiplier": 5.0,
            "knowledge_availability_ratio": 75.0,
        }
    }

    report = InsightEngine.generate_report_markdown(dummy_metrics)

    assert "# SharedMemory Fact Report" in report
    assert "検索ヒット率 (Hit Rate)" in report
    assert "85.0%" in report
    assert "活用係数 (Reuse Multiplier)" in report
    assert "5.0x" in report
    assert "XXドル" not in report # Should not contain speculative monetary values
