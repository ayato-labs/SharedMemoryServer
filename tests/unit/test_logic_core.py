import pytest

from shared_memory.logic import read_memory_core, save_memory_core


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_full_flow(fake_llm):
    """
    Test save_memory_core logic using FakeGeminiClient (No MagicMock).
    """
    # 1. Setup Input
    entities = [{"name": "UnitNode", "description": "A node for unit testing"}]
    observations = ["This is a test observation for UnitNode"]
    bank_files = {"unit_test.md": "# Unit Test\nThis is content."}

    # 2. Execute
    result = await save_memory_core(
        entities=entities, observations=observations, bank_files=bank_files, agent_id="test_agent"
    )

    # 3. Verify Result Message
    assert "Saved 1 entities" in result
    assert "bank files" in result.lower()

    # 4. Verify Persistence via read_memory_core
    search_result = await read_memory_core(query="UnitNode")

    # Check entities
    found_entities = search_result["graph"]["entities"]
    assert any(e["name"] == "UnitNode" for e in found_entities)

    # Check bank files
    found_bank = search_result["bank"]
    assert "unit_test.md" in found_bank
    assert "Unit Test" in found_bank["unit_test.md"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_shorthand(fake_llm):
    """Test string shorthands for entities and observations."""
    result = await save_memory_core(
        entities=["ShorthandNode"], observations=["Shorthand observation"], agent_id="test_agent"
    )

    assert "Saved 1 entities" in result

    search_result = await read_memory_core(query="ShorthandNode")
    assert any(e["name"] == "ShorthandNode" for e in search_result["graph"]["entities"])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_ai_failure(fake_llm):
    """Test behavior when AI/Embedding computation fails."""
    # Inject error into fake client
    fake_llm.models.set_error("embed_content", Exception("API Timeout"))

    result = await save_memory_core(entities=["FailNode"], agent_id="test_agent")

    # In Phase 1, if embed_content fails, the whole save_memory_core returns early with "AI Error"
    assert "AI Error" in result
    assert "API Timeout" in result

    # Verify nothing was saved (as it returned before Phase 2)
    search_result = await read_memory_core(query="FailNode")
    assert not any(e["name"] == "FailNode" for e in search_result["graph"]["entities"])
