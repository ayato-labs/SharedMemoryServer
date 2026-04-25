from shared_memory.logic import normalize_bank_files


def test_normalize_bank_files_dict_format():
    # Standard dict format
    input_data = {"test.md": "content"}
    expected = {"test.md": "content"}
    assert normalize_bank_files(input_data) == expected


def test_normalize_bank_files_single_file_dict():
    # Single file passed as a dict with keys
    input_data = {"filename": "test.md", "content": "hello"}
    expected = {"test.md": "hello"}
    assert normalize_bank_files(input_data) == expected

    # Using 'name' and 'text'
    input_data = {"name": "test2.md", "text": "world"}
    expected = {"test2.md": "world"}
    assert normalize_bank_files(input_data) == expected


def test_normalize_bank_files_list_of_explicit_dicts():
    # List of dicts with synonyms
    input_data = [
        {"filename": "a.md", "content": "aaa"},
        {"name": "b.md", "text": "bbb"},
        {"title": "c.md", "body": "ccc"},
    ]
    expected = {"a.md": "aaa", "b.md": "bbb", "c.md": "ccc"}
    assert normalize_bank_files(input_data) == expected


def test_normalize_bank_files_list_of_simple_dicts():
    # List of single-entry dicts
    input_data = [{"file1.md": "content1"}, {"file2.md": "content2"}]
    expected = {"file1.md": "content1", "file2.md": "content2"}
    assert normalize_bank_files(input_data) == expected


def test_normalize_bank_files_mixed_and_invalid():
    # Mixed valid and invalid entries
    input_data = [
        {"filename": "valid.md", "content": "yes"},
        "not a dict",
        {"no_content": "skip me"},
        {"filename": "no_content_too"},
    ]
    # 'no_content' is not in ['filename', 'name', 'title', 'content', 'text', 'body']
    # So Pattern B will pick up {"no_content": "skip me"} as filename="no_content", content="skip me"
    # To strictly test "skipping invalid items", we need items that have no content synonyms AND more than 1 key,
    # or items with a key in the ignore list.

    # Let's verify the current behavior for these specific items:
    res = normalize_bank_files(input_data)
    assert res["valid.md"] == "yes"
    assert res["no_content"] == "skip me"
    # {"filename": "no_content_too"} has len=1, but key="filename" is in ignore list -> skipped.
    assert "no_content_too" not in res


def test_normalize_bank_files_auto_naming():
    # Missing filename should trigger auto-naming
    input_data = [{"content": "first"}, {"content": "second"}]
    result = normalize_bank_files(input_data)
    assert "derived_knowledge_0.md" in result
    assert result["derived_knowledge_0.md"] == "first"
    assert "derived_knowledge_1.md" in result
    assert result["derived_knowledge_1.md"] == "second"


def test_normalize_bank_files_empty():
    assert normalize_bank_files(None) == {}
    assert normalize_bank_files([]) == {}
    assert normalize_bank_files({}) == {}
