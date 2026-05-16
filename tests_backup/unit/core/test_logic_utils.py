import pytest

from ripen.core.logic import (
    normalize_bank_files,
    normalize_entities,
    normalize_observations,
)


@pytest.mark.unit
class TestLogicNormalizationHard:
    """
    Intentionally harsh tests for normalization logic.
    Focuses on malformed, deeply nested, or unconventional formats.
    """

    def test_normalize_entities_harsh(self):
        # Empty and None
        assert normalize_entities(None) == []
        assert normalize_entities([]) == []

        # String mix
        inputs = [
            "Simple Entity",
            {"name": "Dict Entity", "type": "person"},
            {"id": "ID Entity", "desc": "Using id and desc"},
            {"title": "Title Entity", "content": "Using title and content"},
            # Malformed but should survive
            {"garbage": "value"},
            None,
            123,  # Invalid type should be ignored by the loop logic
        ]
        results = normalize_entities(inputs)

        # "Simple Entity" -> {"name": "Simple Entity", "entity_type": "concept", "description": ""}
        assert results[0]["name"] == "Simple Entity"
        assert results[0]["entity_type"] == "concept"

        # "Dict Entity"
        assert results[1]["name"] == "Dict Entity"
        assert results[1]["entity_type"] == "person"

        # "ID Entity"
        assert results[2]["name"] == "ID Entity"
        assert results[2]["description"] == "Using id and desc"

        # "Title Entity"
        assert results[3]["name"] == "Title Entity"
        assert results[3]["description"] == "Using title and content"

        # "garbage" -> name is 'Unnamed' (e.get("name") or e.get("id") or e.get("title") or "Unnamed")
        assert results[4]["name"] == "Unnamed"
        assert results[4]["entity_type"] == "concept"

    def test_normalize_observations_harsh(self):
        inputs = [
            "Global observation string",
            {"content": "Standard obs", "entity_name": "Entity1"},
            {"observation": "Synonym obs", "entity": "Entity2"},
            {"text": "Another synonym", "entity_name": "Entity3"},
            {"content": ""},  # Empty content should be filtered out by normalize_observation_item
            {},  # Empty dict should be None
            None,
        ]
        results = normalize_observations(inputs)

        # String -> Global
        assert results[0]["content"] == "Global observation string"
        assert results[0]["entity_name"] == "Global"

        # Standard
        assert results[1]["content"] == "Standard obs"
        assert results[1]["entity_name"] == "Entity1"

        # Synonyms
        assert results[2]["content"] == "Synonym obs"
        assert results[2]["entity_name"] == "Entity2"

        assert results[3]["content"] == "Another synonym"
        assert results[3]["entity_name"] == "Entity3"

        # Length check (others should be skipped)
        assert len(results) == 4

    def test_normalize_bank_files_harsh(self):
        # Deeply malformed list
        inputs = [
            {"filename": "a.md", "content": "A"},
            {"file_with_no_synonym": "B"},  # Pattern B: filename="file_with_no_synonym"
            {"filename": "C"},  # Pattern B: but 'filename' is in ignore list -> Skip
            {"content": "D"},  # Pattern A: content="D", filename=None -> auto-names
            # Wait, let's re-examine normalize_bank_files code for Pattern A vs B
        ]
        # In code:
        # filename = item.get("filename") or item.get("name") or item.get("title")
        # content = item.get("content") or item.get("text") or item.get("body")
        # if content: ... result[filename or auto_name] = content

        results = normalize_bank_files(inputs)
        assert results["a.md"] == "A"
        assert results["file_with_no_synonym"] == "B"

        # {"content": "D"} -> Pattern A: content="D", filename=None
        # -> auto-names as "derived_knowledge_3.md"
        assert results["derived_knowledge_3.md"] == "D"

    def test_normalize_bank_files_nested_madness(self):
        # Users might pass something really weird
        input_data = {
            "file.md": {"not_a_string": "oops"},  # v is not a string
            "valid.md": "good content",
            "empty.md": "",  # v is falsy
        }
        # In code: return {str(k): str(v) for k, v in bank_files.items() if v}
        results = normalize_bank_files(input_data)
        assert results["file.md"] == "{'not_a_string': 'oops'}"
        assert results["valid.md"] == "good content"
        assert "empty.md" not in results
