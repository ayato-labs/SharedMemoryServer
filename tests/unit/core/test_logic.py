from unittest.mock import patch

import pytest

from shared_memory.core import logic
from tests.unit.fake_client import FakeGeminiClient


@pytest.fixture
def fake_client():
    return FakeGeminiClient()


@pytest.mark.asyncio
async def test_normalize_entities():
    # Test strings
    input_entities = ["Python", {"name": "FastMCP", "type": "Library"}]
    normalized = logic.normalize_entities(input_entities)

    assert len(normalized) == 2
    assert normalized[0]["name"] == "Python"
    assert normalized[0]["entity_type"] == "concept"
    assert normalized[1]["name"] == "FastMCP"
    assert normalized[1]["entity_type"] == "Library"


@pytest.mark.asyncio
async def test_normalize_observations():
    input_obs = ["It works", {"observation": "Real fact", "entity": "Test"}]
    normalized = logic.normalize_observations(input_obs)

    assert len(normalized) == 2
    assert normalized[0]["content"] == "It works"
    assert normalized[0]["entity_name"] == "Global"
    assert normalized[1]["content"] == "Real fact"
    assert normalized[1]["entity_name"] == "Test"


@pytest.mark.asyncio
async def test_normalize_bank_files():
    # Various formats
    input_files = {"readme.md": "Hello", "data.json": '{"a": 1}'}
    normalized = logic.normalize_bank_files(input_files)
    assert normalized["readme.md"] == "Hello"

    input_list = [{"filename": "list.md", "content": "list content"}]
    normalized_list = logic.normalize_bank_files(input_list)
    assert normalized_list["list.md"] == "list content"


@pytest.mark.asyncio
async def test_save_memory_core_basic(fake_client):
    # Use patch to inject fake client WITHOUT MagicMock for the logic being tested
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_client):
        result = await logic.save_memory_core(
            entities=["UnitEntity"],
            observations=[{"content": "Unit content", "entity_name": "UnitEntity"}],
        )
        assert "Saved 1 entities" in result
        assert "Saved 1 observations" in result


@pytest.mark.asyncio
async def test_save_memory_core_ai_error():
    # Simulate AI failure by patching the bulk computation directly
    with patch(
        "shared_memory.core.logic.compute_embeddings_bulk", side_effect=Exception("AI Down")
    ):
        result = await logic.save_memory_core(entities=["ErrorEntity"])
        assert "AI Error" in result
