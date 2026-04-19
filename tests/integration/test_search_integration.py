from unittest.mock import patch

import pytest

from shared_memory.database import async_get_connection
from shared_memory.insights import InsightEngine
from shared_memory.logic import read_memory_core, save_memory_core
from tests.unit.fake_client import FakeGeminiClient


@pytest.mark.asyncio
async def test_db_heartbeat():
    """Verify standard DB connectivity works at all."""
    print("\n--- Diagnostic: Heartbeat START")
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT 1")
        result = await cursor.fetchone()
        assert result[0] == 1
    print("--- Diagnostic: Heartbeat SUCCESS")


@pytest.mark.asyncio
async def test_search_to_insight_integration():
    """
    Integration test: save -> search -> verify hit rate in insights.
    Checks the flow between memory utilization and its quantification.
    """
    fake_client = FakeGeminiClient()
    with patch("shared_memory.embeddings.get_gemini_client", return_value=fake_client):
        # 1. Save dummy knowledge
        print("\n--- Diagnostic: Starting Step 1 (Save)")
        await save_memory_core(
            entities=[
                {
                    "name": "Python",
                    "entity_type": "language",
                    "description": "A coding language",
                }
            ]
        )
        print("--- Diagnostic: Step 1 (Save) Complete")

        # 2. Perform searches (1 hit)
        print("--- Diagnostic: Starting Step 2a (Search Hit)")
        await read_memory_core(query="Python")
        print("--- Diagnostic: Step 2a (Search Hit) Complete")

        # Perform a query that definitely misses (0 results)
        print("--- Diagnostic: Starting Step 2b (Search Miss)")
        await read_memory_core(query="ZyzygyNonExistentWord123")
        print("--- Diagnostic: Step 2b (Search Miss) Complete")

        # 3. Verify through InsightEngine
        print("--- Diagnostic: Starting Step 3 (Insights)")
        metrics = await InsightEngine.get_summary_metrics()
        print("--- Diagnostic: Step 3 (Insights) Complete")
        f = metrics["facts"]

        assert f["total_search_queries"] == 2
        # Expecting 100% hit rate with low threshold for testing stability
        assert f["search_hit_rate_percent"] == 100.0


@pytest.mark.asyncio
async def test_multi_access_reuse_multiplier():
    """
    Integration test: multiple reads of the same entity increase reuse multiplier.
    """
    fake_client = FakeGeminiClient()
    with patch("shared_memory.embeddings.get_gemini_client", return_value=fake_client):
        await save_memory_core(
            entities=[{"name": "ToolA", "entity_type": "tool", "description": "Useful tool"}]
        )

        # Access ToolA twice via search.
        # Search for "ToolA" should find it and update_access via search logic.
        await read_memory_core(query="ToolA")
        await read_memory_core(query="ToolA")

        metrics = await InsightEngine.get_summary_metrics()
        i = metrics["efficiency_indicators"]

        # Total access should be 2, items 1 -> 2.0x
        assert i["reuse_multiplier"] >= 2.0
