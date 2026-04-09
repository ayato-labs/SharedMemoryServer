import os
import aiofiles
import pytest

from shared_memory.bank import initialize_bank, read_bank_data, save_bank_files
from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import repair_memory_core as repair_memory_logic
from shared_memory.utils import get_bank_dir


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_initialize_bank(mock_gemini):
    await initialize_bank()
    bank_dir = get_bank_dir()
    assert os.path.exists(bank_dir)
    # Check for a core file
    assert os.path.exists(os.path.join(bank_dir, "projectBrief.md"))


@pytest.mark.asyncio
async def test_save_bank_files(mock_gemini):
    async with await async_get_connection() as conn:
        files = {"test.md": "# Test Content"}
        res = await save_bank_files(files, "test_agent", conn)
        await conn.commit()

        assert "Updated 1 bank files" in res

        # Verify in DB
        cursor = await conn.execute(
            "SELECT content FROM bank_files WHERE filename = 'test.md'"
        )
        row = await cursor.fetchone()
        assert row[0] == "# Test Content"

    # Verify on disk
    path = os.path.join(get_bank_dir(), "test.md")
    assert os.path.exists(path)
    async with aiofiles.open(path, encoding="utf-8") as f:
        content = await f.read()
        assert content == "# Test Content"


@pytest.mark.asyncio
async def test_read_bank_data(mock_gemini):
    # Save a file first
    async with await async_get_connection() as conn:
        await save_bank_files({"read_me.md": "Special content"}, "test_agent", conn)
        await conn.commit()

    data = await read_bank_data(query="Special")
    assert "read_me.md" in data
    assert data["read_me.md"] == "Special content"

    # Query mismatch
    data_none = await read_bank_data(query="NonExistent")
    assert len(data_none) == 0


@pytest.mark.asyncio
async def test_repair_memory():
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO bank_files (filename, content) VALUES ('missing.md', 'I should be on disk')"
        )
        await conn.commit()

    bank_dir = get_bank_dir()
    missing_path = os.path.join(bank_dir, "missing.md")
    if os.path.exists(missing_path):
        os.remove(missing_path)

    res = await repair_memory_logic()
    assert "Restored 1 files" in res
    assert os.path.exists(missing_path)
