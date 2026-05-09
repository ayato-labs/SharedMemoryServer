from unittest.mock import patch

import pytest

from ripen.core import logic
from tests.unit.fake_client import FakeGeminiClient


@pytest.mark.asyncio
async def test_save_memory_harsh_invalid_inputs():
    """
    Test with garbage inputs to ensure robustness.
    """
    # Test with None
    res = await logic.save_memory_core(entities=None, observations=None)
    # The current implementation returns empty string if nothing to save
    assert res == ""

    # Test with empty strings in list
    res = await logic.save_memory_core(
        entities=["", "  "], observations=[{"content": "", "entity_name": ""}]
    )
    # Empty strings are filtered but might be reported as "skipped" or "errors"
    # depending on implementation.
    # Based on actual run: 'Saved 0 entities (Errors: 2)'
    assert "Saved 0" in res


@pytest.mark.asyncio
async def test_save_memory_harsh_ai_repeated_errors():
    """
    Test how it handles persistent AI errors.
    Expectation: The system remains resilient and persists the raw data
    even if vector embedding fails (falls back to keyword-only search).
    """
    fake_client = FakeGeminiClient()
    fake_client.models.set_error("embed_content", Exception("Rate Limit Exceeded"))

    with patch("ripen.infra.embeddings.get_gemini_client", return_value=fake_client):
        # We also need to patch compute_embeddings_bulk if it's used directly
        # actually save_memory_core uses logic_module.compute_embedding which uses
        # embeddings.compute_embedding which uses get_gemini_client().

        # 実行
        res = await logic.save_memory_core(
            entities=[{"name": "ResilientNode", "description": "AI fails but I live"}]
        )
        # Should report success because data was saved to DB
        assert "Saved 1 entities" in res

        # 裏取り: 本当にDBに保存されているか
        from ripen.infra.database import async_get_connection

        async with await async_get_connection() as conn:
            cursor = await conn.execute("SELECT name FROM entities WHERE name='ResilientNode'")
            assert (await cursor.fetchone()) is not None


@pytest.mark.asyncio
async def test_save_memory_harsh_data_corruption_simulation():
    """
    Test with malformed observation dictionaries.
    """
    malformed_obs = [{"wrong_key": "data"}, ["not", "a", "dict"], "just a string"]

    try:
        res = await logic.save_memory_core(observations=malformed_obs)
        # Should handle it gracefully, likely saving the valid-looking ones or skipping
        assert isinstance(res, str)
    except Exception as e:
        pytest.fail(f"save_memory_core crashed with malformed data: {e}")


@pytest.mark.asyncio
async def test_concurrent_saves_pressure():
    """
    Simulate many concurrent saves to check for DB locks (already has retry logic).
    """
    import asyncio

    tasks = []
    for i in range(10):
        tasks.append(
            logic.save_memory_core(
                entities=[f"ConcurrentEntity{i}"],
                observations=[{"content": f"Data {i}", "entity_name": f"ConcurrentEntity{i}"}],
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            pytest.fail(f"Concurrent save failed: {res}")
        assert "Saved" in res
