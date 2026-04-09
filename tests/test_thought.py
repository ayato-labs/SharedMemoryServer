import os
import aiosqlite
import pytest
import tempfile

from shared_memory.thought_logic import (
    get_thought_history,
    init_thoughts_db,
    process_thought_core,
)


@pytest.fixture
async def temp_thoughts_db(monkeypatch):
    """Provides a temporary thoughts database path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("THOUGHTS_DB_PATH", path)
    await init_thoughts_db()
    yield path

    if os.path.exists(path):
        os.remove(path)
    for ext in ["-wal", "-shm"]:
        if os.path.exists(path + ext):
            try:
                os.remove(path + ext)
            except OSError:
                pass


@pytest.mark.asyncio
async def test_init_thoughts_db(temp_thoughts_db):
    """Verifies that the thoughts database and table are created correctly."""
    assert os.path.exists(temp_thoughts_db)
    async with aiosqlite.connect(temp_thoughts_db) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='thought_history'"
        )
        assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_process_thought_basic(temp_thoughts_db):
    """Tests basic linear thought processing."""
    result = await process_thought_core(
        thought="First step",
        thought_number=1,
        total_thoughts=3,
        next_thought_needed=True,
        session_id="test_session",
    )

    assert result["thoughtNumber"] == 1
    assert result["totalThoughts"] == 3
    assert result["nextThoughtNeeded"] is True
    assert result["thoughtHistoryLength"] == 1

    history = await get_thought_history("test_session")
    assert len(history) == 1
    assert history[0]["thought"] == "First step"


@pytest.mark.asyncio
async def test_process_thought_with_revision(temp_thoughts_db):
    """Tests thought revision processing."""
    # First thought
    await process_thought_core(
        thought="Original thought",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="rev_session",
    )

    # Revision thought
    result = await process_thought_core(
        thought="Revised thought",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        is_revision=True,
        revises_thought=1,
        session_id="rev_session",
    )

    assert result["thoughtNumber"] == 2
    assert result["nextThoughtNeeded"] is False

    history = await get_thought_history("rev_session")
    assert len(history) == 2
    assert history[1]["is_revision"] == 1
    assert history[1]["revises_thought"] == 1


@pytest.mark.asyncio
async def test_process_thought_with_branch(temp_thoughts_db):
    """Tests thought branching processing."""
    # Branching thought
    result = await process_thought_core(
        thought="Alternative path",
        thought_number=2,
        total_thoughts=5,
        next_thought_needed=True,
        branch_from_thought=1,
        branch_id="branch_A",
        session_id="branch_session",
    )

    assert "branch_A" in result["branches"]

    history = await get_thought_history("branch_session")
    assert history[0]["branch_id"] == "branch_A"
    assert history[0]["branch_from_thought"] == 1
