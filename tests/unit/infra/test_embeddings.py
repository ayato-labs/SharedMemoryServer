from unittest.mock import patch

import pytest

from shared_memory.infra.embeddings import compute_embedding, compute_embeddings_bulk


@pytest.mark.asyncio
async def test_compute_embedding_isolated(fake_llm_client):
    """Verify compute_embedding using FakeGeminiClient (no MagicMock)."""
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        vector = await compute_embedding("test text")
        assert len(vector) == 768
        assert isinstance(vector[0], float)


@pytest.mark.asyncio
async def test_compute_embeddings_bulk_isolated(fake_llm_client):
    """Verify compute_embeddings_bulk using FakeGeminiClient."""
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        texts = ["apple", "banana", "cherry"]
        vectors = await compute_embeddings_bulk(texts)
        assert len(vectors) == 3
        for v in vectors:
            assert len(v) == 768


@pytest.mark.asyncio
async def test_compute_embedding_empty_input(fake_llm_client):
    """Verify behavior with empty input."""
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        vector = await compute_embedding("")
        assert len(vector) == 768
