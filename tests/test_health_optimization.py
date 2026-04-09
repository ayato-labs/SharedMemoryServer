from unittest.mock import patch

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.embeddings import compute_embedding, compute_embeddings_bulk
from shared_memory.health import get_comprehensive_diagnostics
from shared_memory.logic import get_memory_health_core


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_comprehensive_diagnostics(mock_gemini):
    with patch(
        "shared_memory.health.check_disk_usage",
        return_value={
            "dir": "/tmp",
            "total": 10**12,
            "used": 0,
            "free": 10**12,
            "percent_free": 100.0,
        },
    ):
        # Mock Gemini to be healthy
        mock_gemini.models.list.return_value = [
            type("Model", (), {"name": "models/gemini-pro"})
        ]

        report = await get_comprehensive_diagnostics()
    assert report["status"] == "healthy"
    assert "database" in report["components"]
    assert "storage" in report["components"]
    assert "api" in report["components"]
    assert report["components"]["api"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_embedding_cache_integrity(mock_gemini):
    text = "Find me in the cache"
    mock_vec = [0.5] * 768

    # Setup mock
    class MockEmb:
        def __init__(self, values):
            self.values = values

    class MockResp:
        def __init__(self, embs):
            self.embeddings = embs

    mock_gemini.models.embed_content.return_value = MockResp([MockEmb(mock_vec)])
    mock_gemini.models.embed_content.side_effect = None

    # 1. First call (API)
    vec1 = await compute_embedding(text)
    assert vec1 == mock_vec
    assert mock_gemini.models.embed_content.call_count == 1

    # 2. Second call (Cache)
    vec2 = await compute_embedding(text)
    assert vec2 == mock_vec
    assert mock_gemini.models.embed_content.call_count == 1  # Still 1

    # 3. Verify in DB
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT count(*) FROM embedding_cache")
        row = await cursor.fetchone()
        assert row[0] == 1


@pytest.mark.asyncio
async def test_bulk_embedding_optimization(mock_gemini):
    texts = ["Bulk 1", "Bulk 2", "Already Cached"]
    mock_vecs = [[0.1] * 768, [0.2] * 768, [0.3] * 768]

    # Pre-cache "Already Cached"
    await compute_embedding("Already Cached")
    # Reset mock after pre-caching
    mock_gemini.models.embed_content.reset_mock()

    class MockEmb:
        def __init__(self, values):
            self.values = values

    class MockResp:
        def __init__(self, embs):
            self.embeddings = embs

    # The API should only be called for "Bulk 1" and "Bulk 2"
    mock_gemini.models.embed_content.return_value = MockResp(
        [MockEmb(mock_vecs[0]), MockEmb(mock_vecs[1])]
    )

    results = await compute_embeddings_bulk(texts)

    assert len(results) == 3
    # Check if API was called with ONLY the missing 2 texts
    call_args = mock_gemini.models.embed_content.call_args
    assert len(call_args.kwargs["contents"]) == 2
    assert "Bulk 1" in call_args.kwargs["contents"]
    assert "Bulk 2" in call_args.kwargs["contents"]
    assert "Already Cached" not in call_args.kwargs["contents"]


@pytest.mark.asyncio
async def test_logic_health_integration(mock_gemini):
    mock_gemini.models.list.return_value = [
        type("Model", (), {"name": "models/gemini-pro"})
    ]

    with patch(
        "shared_memory.health.check_disk_usage",
        return_value={
            "dir": "/tmp",
            "total": 10**12,
            "used": 0,
            "free": 10**12,
            "percent_free": 100.0,
        },
    ):
        health = await get_memory_health_core()
        assert "management_stats" in health
        assert "issues" in health
        assert health["status"] == "healthy"
