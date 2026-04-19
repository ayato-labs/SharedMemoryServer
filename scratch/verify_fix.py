
import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch
from shared_memory import logic, database

class TestErrorHandling(unittest.IsolatedAsyncioTestCase):
    async def test_db_init_failure_message(self):
        # Simulate DB init failure
        with patch("shared_memory.logic.init_db", side_effect=Exception("Simulated DB Init Failure")):
            res = await logic.save_memory_core(entities=[{"name": "Test"}])
            print(f"\nDB Init Failure Output: {res}")
            self.assertIn("Critical Error: Could not initialize database.", res)

    async def test_api_failure_message(self):
        # Simulate API failure during embedding
        # We need to bypass init_db success but fail at embedding
        with patch("shared_memory.logic.init_db", return_value=None):
            with patch("shared_memory.logic.compute_embeddings_bulk", side_effect=Exception("API Key Invalid or Timeout")):
                res = await logic.save_memory_core(entities=[{"name": "Test", "description": "desc"}])
                print(f"API Failure Output: {res}")
                self.assertIn("AI Error: Connectivity failed", res)

    async def test_read_memory_db_locked_message(self):
        # Simulate DB Lock during read
        import aiosqlite
        with patch("shared_memory.logic.init_db", return_value=None):
            with patch("shared_memory.search.perform_search", side_effect=aiosqlite.OperationalError("database is locked")):
                res = await logic.read_memory_core(query="test")
                print(f"DB Lock Output: {res}")
                self.assertEqual(res, "Database Error: Database is currently locked by another process.")

if __name__ == "__main__":
    unittest.main()
