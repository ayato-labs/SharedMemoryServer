import pytest

from shared_memory.core.graph import extract_hashtags, save_tags
from tests.unit.fake_client import FakeGeminiClient

pytestmark = pytest.mark.unit

@pytest.mark.asyncio
async def test_extract_hashtags_success(monkeypatch):
    """Verify hashtag extraction using a FakeGeminiClient (No MagicMock)."""
    fake_client = FakeGeminiClient()
    # Set fake AI response
    fake_client.models.set_response("generate_content", '["#ai", "Machine Learning"]')
    
    monkeypatch.setattr("shared_memory.core.graph.get_gemini_client", lambda: fake_client)
    
    tags = await extract_hashtags("This is a post about AI and Machine Learning.")
    
    assert "#ai" in tags
    assert "#machinelearning" in tags # Normalization test
    assert len(tags) <= 5

@pytest.mark.asyncio
async def test_extract_hashtags_empty_content():
    """Verify it returns empty list for short content without calling AI."""
    tags = await extract_hashtags("too short")
    assert tags == []

@pytest.mark.asyncio
async def test_save_tags_persistence(db_conn):
    """Verify tags are correctly inserted into the DB."""
    content_id = "test_entity"
    tags = ["#test", "#unit"]
    
    await save_tags(content_id, "entity", tags, db_conn)
    
    cursor = await db_conn.execute("SELECT tag FROM tags WHERE content_id = ?", (content_id,))
    rows = await cursor.fetchall()
    saved_tags = [r[0] for r in rows]
    
    assert "#test" in saved_tags
    assert "#unit" in saved_tags
    assert len(saved_tags) == 2
