from unittest.mock import patch

import pytest

from ripen.infra.embeddings import compute_embedding, compute_embeddings_bulk


@pytest.mark.asyncio
async def test_compute_embedding_isolated(fake_llm_client, monkeypatch):
    """Verify compute_embedding using FakeGeminiClient (no MagicMock)."""
    # Use monkeypatch to set environment variables that the settings property reads
    monkeypatch.setenv("EMBEDDING_ENGINE", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    with patch("ripen.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        vector = await compute_embedding("test text")
        assert len(vector) == 768
        assert isinstance(vector[0], float)


@pytest.mark.asyncio
async def test_compute_embeddings_bulk_isolated(fake_llm_client, monkeypatch):
    """Verify compute_embeddings_bulk using FakeGeminiClient."""
    monkeypatch.setenv("EMBEDDING_ENGINE", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    with patch("ripen.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        texts = ["apple", "banana", "cherry"]
        vectors = await compute_embeddings_bulk(texts)
        assert len(vectors) == 3
        for v in vectors:
            assert len(v) == 768


@pytest.mark.asyncio
async def test_compute_embedding_empty_input(fake_llm_client, monkeypatch):
    """Verify behavior with empty input."""
    monkeypatch.setenv("EMBEDDING_ENGINE", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    with patch("ripen.infra.embeddings.get_gemini_client", return_value=fake_llm_client):
        vector = await compute_embedding("")
        assert len(vector) == 768
