import pytest

from shared_memory.database import init_db
from shared_memory.logic import save_memory_core
from shared_memory.server import sequential_thinking
from shared_memory.thought_logic import init_thoughts_db


@pytest.fixture(autouse=True)
async def setup_all_db():
    await init_db(force=True)
    await init_thoughts_db(force=True)


@pytest.mark.asyncio
async def test_sequential_knowledge_injection_integration():
    """
    Integration test:
    1. Save knowledge about a project.
    2. Perform sequential thinking.
    3. Verify that the 'related_knowledge' contains the content saved in step 1.
    """
    # 1. Save data via core logic
    await save_memory_core(
        entities=[{"name": "ProjectX", "description": "A secret project about AI"}],
        observations=[
            {"entity_name": "ProjectX", "content": "Uses shared memory for context"}
        ],
    )

    # 2. Trigger sequential thinking with a query that should match
    # Searches for related knowledge based on the 'thought'
    res = await sequential_thinking(
        thought="I am starting to analyze ProjectX architecture.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
    )

    # 3. Verify knowledge injection
    related = res.get("related_knowledge", [])
    assert len(related) > 0

    found_content = False
    for item in related:
        if "ProjectX" in item.get("id", ""):
            # Check for content field (the fix we made earlier)
            assert "content" in item
            assert (
                "secret project" in item["content"]
                or "shared memory" in item["content"]
            )
            found_content = True

    assert found_content, (
        "Knowledge content was not injected into sequential thinking result"
    )
