from unittest.mock import patch

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.exceptions import DatabaseError, SharedMemoryError
from shared_memory.logic import save_memory_core
from shared_memory.utils import get_db_path


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_huge_data_limit(mock_gemini):
    """
    Test saving an entity with an extremely large description (1MB).
    Verifies that SQLite handles large blobs and the system doesn't crash.
    """
    large_desc = "X" * (1024 * 1024)  # 1MB
    entities = [
        {"name": "HugeEntity", "entity_type": "Data", "description": large_desc}
    ]

    res = await save_memory_core(entities=entities)
    assert "Saved 1 entities" in res

    # Read it back
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT description FROM entities WHERE name = 'HugeEntity'"
        )
        row = await cursor.fetchone()
        assert len(row[0]) == len(large_desc)


@pytest.mark.asyncio
async def test_database_corruption_resilience(mock_gemini):
    """
    Test what happens if the database file is not a valid SQLite database.
    """
    db_path = get_db_path()

    # Close any connections and overwrite with garbage
    with open(db_path, "wb") as f:
        f.write(b"NOT_A_DATABASE_FILE_GARBAGE")

    # Attempting to save should raise a DatabaseError
    with pytest.raises(DatabaseError) as exc:
        await save_memory_core(entities=[{"name": "Fail", "entity_type": "Test"}])
    assert "Transaction failed" in str(exc.value)


@pytest.mark.asyncio
async def test_bank_dir_read_only(mock_gemini):
    """
    Test what happens if the bank directory is read-only.
    """
    # We mock aiofiles.open to simulate permission error
    with patch("aiofiles.open", side_effect=PermissionError("Permission Denied")):
        bank_files = {"readonly.md": "Should fail"}
        with pytest.raises(SharedMemoryError) as exc:
            await save_memory_core(bank_files=bank_files)
        assert "Unexpected error" in str(exc.value)


@pytest.mark.asyncio
async def test_invalid_json_observations(mock_gemini):
    """
    Test sending observations that are not properly structured.
    GIGO Prevention test.
    """
    # Missing required keys (no entity_name or content)
    bad_observations = [{"wrong_key": "No entity name"}]

    res = await save_memory_core(observations=bad_observations)
    assert "Saved 0 observations" in res
    assert "Errors: 1" in res
