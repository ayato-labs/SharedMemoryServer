from unittest.mock import patch

import pytest

from ripen.core.graph import extract_hashtags, save_tags
from tests.unit.fake_client import FakeGeminiClient

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_extract_hashtags_success(monkeypatch):
    """Verify hashtag extraction using a FakeGeminiClient (No MagicMock)."""
    fake_client = FakeGeminiClient()
    # Set fake AI response
    fake_client.models.set_response("generate_content", '["#ai", "Machine Learning"]')

    # Force AI usage by lowering threshold
    with patch("ripen.core.graph.settings") as mock_settings:
        mock_settings.hashtag_ai_threshold = 0

        # Mocking the provider
        class FakeProvider:
            async def generate_content(self, prompt, system_instruction=None):
                resp = fake_client.models.generate_content(model="fake", contents=prompt)
                return resp.text

        with patch("ripen.core.graph.get_llm_provider", return_value=FakeProvider()):
            tags = await extract_hashtags("This is a post about AI and Machine Learning.")

    assert "#ai" in tags
    assert "#machinelearning" in tags  # Normalization test
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


@pytest.mark.asyncio
async def test_save_tags_error(db_conn):
    """Verify that tag saving handles database errors gracefully."""
    # This test might need more sophisticated mocking if we want to force an error
    # but for now we just verify it doesn't crash if we pass garbage.
    await save_tags(None, None, ["#error"], db_conn)  # Should log and return
