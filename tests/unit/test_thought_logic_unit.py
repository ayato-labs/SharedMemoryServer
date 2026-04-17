import pytest

from shared_memory.thought_logic import (
    get_thought_history,
    init_thoughts_db,
    process_thought_core,
)


@pytest.fixture(autouse=True)
async def setup_thoughts_db():
    await init_thoughts_db(force=True)


@pytest.mark.asyncio
async def test_process_thought_unit():
    """Verify single thought processing and retrieval."""
    res = await process_thought_core(
        thought="Test thought contents",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
    )
    assert res["thoughtNumber"] == 1

    history = await get_thought_history()
    assert len(history) == 1
    assert history[0]["thought"] == "Test thought contents"


@pytest.mark.asyncio
async def test_thought_sequence_continuity_unit():
    """Verify that multiple thoughts are saved with correct sequence logic."""
    # 1. First thought
    await process_thought_core("Step 1", 1, 3, True)
    # 2. Second thought
    await process_thought_core("Step 2", 2, 3, True)

    history = await get_thought_history()
    assert len(history) == 2
    assert history[0]["thought_number"] == 1
    assert history[1]["thought_number"] == 2


@pytest.mark.asyncio
async def test_invalid_thought_handling_unit():
    """Severe test: invalid sequence parameters."""
    # Note: process_thought_core doesn't currently raise ValueError for thought_number,
    # it just processes it. But if we want it to be "tough", we should probably
    # add these validations or just test its current behavior with weird inputs.

    # Large numbers
    res = await process_thought_core("Huge", 999999, 1, False)
    assert res["thoughtNumber"] == 999999

    # Missing revision
    res = await process_thought_core(
        "Revision", 2, 2, False, is_revision=True, revises_thought=1
    )
    assert "error" in res
    assert "Invalid revision" in res["error"]
