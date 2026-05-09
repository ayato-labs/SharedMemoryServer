import pytest

from ripen.common.utils import escape_fts5_query
from ripen.core.search import perform_keyword_search


def test_escape_fts5_query():
    assert escape_fts5_query("it's") == '"it\'s"'
    assert escape_fts5_query('a "test"') == '"a" """test"""'
    assert escape_fts5_query("hello world") == '"hello" "world"'
    assert escape_fts5_query("") == ""
    assert escape_fts5_query("   ") == ""
    assert escape_fts5_query('"') == '""""'

@pytest.mark.asyncio
async def test_perform_keyword_search_with_special_chars():
    # This test ensures that perform_keyword_search does not crash with special characters
    # Even if no results are found, it should not raise OperationalError
    try:
        results = await perform_keyword_search("it's a test' with \"quotes\"")
        assert isinstance(results, list)
    except Exception as e:
        pytest.fail(f"perform_keyword_search raised an exception: {e}")

@pytest.mark.asyncio
async def test_perform_keyword_search_empty_query():
    # Should handle empty query gracefully
    results = await perform_keyword_search("")
    assert results == []
