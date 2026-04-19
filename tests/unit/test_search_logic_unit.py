import pytest

from shared_memory.database import init_db
from shared_memory.logic import save_memory_core
from shared_memory.search import perform_keyword_search


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db(force=True)


@pytest.mark.asyncio
async def test_keyword_search_content_injection_unit():
    """
    Verify that perform_keyword_search returns actual content payloads
    for various entity types.
    """
    # 1. Seed data
    await save_memory_core(
        entities=[{"name": "Apple", "description": "A fruit"}],
        observations=[{"entity_name": "Apple", "content": "Red and crunchy"}],
    )

    # 2. Search for "Apple"
    results = await perform_keyword_search("Apple")

    # 3. Verify content injection
    found_apple = False
    found_obs = False

    for hit in results:
        if hit["id"] == "Apple" and hit["source"] == "entities":
            assert "A fruit" in hit["content"]
            found_apple = True
        if hit["source"] == "observations":
            assert "Red and crunchy" in hit["content"]
            found_obs = True

    assert found_apple
    assert found_obs


@pytest.mark.asyncio
async def test_search_empty_query_unit():
    """Verify search behavior with empty or whitespace input."""
    res = await perform_keyword_search("")
    assert res == []

    res = await perform_keyword_search("   ")
    assert res == []


@pytest.mark.asyncio
async def test_search_special_characters_unit():
    """Severe test: search for special Regex-like characters."""
    await save_memory_core(entities=[{"name": "Special_Chars_*?+", "description": "Regex test"}])

    # Should not crash and should find the entity using literal search if possible,
    # or handle gracefully if using regex.
    res = await perform_keyword_search("*?+")
    # Current implementation uses simple keyword matching or SQLite LIKE.
    # We just want to ensure it doesn't crash.
    assert isinstance(res, list)
