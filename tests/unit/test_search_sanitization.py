import pytest
from shared_memory.core.search import sanitize_fts_query

def test_sanitize_fts_query_basic():
    assert sanitize_fts_query("hello world") == '"hello" "world"'

def test_sanitize_fts_query_hyphen():
    # This was the problematic case
    assert sanitize_fts_query("trade-off") == '"trade" "off"'

def test_sanitize_fts_query_special_chars():
    assert sanitize_fts_query("hello @world #tag!") == '"hello" "world" "tag"'

def test_sanitize_fts_query_japanese():
    # Ensure it works with Japanese characters (which \w supports in Python 3)
    assert sanitize_fts_query("こんにちは 世界") == '"こんにちは" "世界"'

def test_sanitize_fts_query_empty():
    assert sanitize_fts_query("") == ""
    assert sanitize_fts_query("   ") == ""
    assert sanitize_fts_query("!!!") == ""

@pytest.mark.asyncio
async def test_perform_keyword_search_with_hyphen(fake_llm):
    # This test ensures that perform_keyword_search doesn't crash with hyphens.
    from shared_memory.core.search import perform_keyword_search
    
    # Even if no data is found, it should NOT raise OperationalError
    # setup_teardown_db (autouse) handles the DB initialization.
    results = await perform_keyword_search("trade-off")
    assert isinstance(results, list)
