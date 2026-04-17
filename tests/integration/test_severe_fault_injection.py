import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import save_memory_core


@pytest.mark.asyncio
async def test_high_concurrency_db_lock_stress():
    """
    Severe Test: Stress test DB lock handling with high concurrency.
    Runs 15 simultaneous writes to trigger retries.
    """
    await init_db(force=True)

    async def write_op(i):
        # Multiple entities to keep the transaction open a bit longer
        entities = [
            {"name": f"Concurrent{i}_{j}", "description": "Stress"} for j in range(5)
        ]
        return await save_memory_core(entities=entities)

    # Launch 15 tasks simultaneously
    tasks = [write_op(i) for i in range(15)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check if any failed with lock error (they shouldn't if retries work)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Concurrency failed with errors: {errors}"

    # Verify count
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT count(*) FROM entities")
        count = (await cursor.fetchone())[0]
        assert count == 15 * 5


@pytest.mark.asyncio
async def test_huge_data_payload_resilience():
    """
    Severe Test: Send a massive string (1MB) to ensure the system handles it.
    """
    huge_string = "X" * (1024 * 1024)  # 1MB
    entities = [{"name": "HugeEntity", "description": huge_string}]

    res = await save_memory_core(entities=entities)
    assert "Saved" in res

    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT description FROM entities WHERE name='HugeEntity'"
        )
        saved_desc = (await cursor.fetchone())[0]
        assert len(saved_desc) == len(huge_string)


@pytest.mark.asyncio
async def test_file_permission_error_handling():
    """
    Severe Test: Mock a PermissionError during bank file saving.
    Ensure DB transaction is rolled back.
    """
    await init_db(force=True)
    entities = [{"name": "RollbackMe", "description": "Fail"}]
    bank_files = {"fail.md": "content"}

    with patch("aiofiles.open", side_effect=PermissionError("Fake Permission Denied")):
        from shared_memory.exceptions import SharedMemoryError

        with pytest.raises(SharedMemoryError):
            await save_memory_core(entities=entities, bank_files=bank_files)

    # Verify rollback
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM entities WHERE name='RollbackMe'")
        assert await cursor.fetchone() is None


@pytest.mark.no_global_mock
@pytest.mark.asyncio
async def test_corrupted_settings_json_resilience():
    """
    Severe Test: Corrupted JSON in settings file should be handled gracefully.
    """
    from shared_memory import embeddings

    # We need to un-mock get_gemini_client for this test or use the real function
    # AND Ensure OS env is empty so it tries to read the file
    with patch.dict(
        os.environ, {"GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""}, clear=False
    ):
        # Temporarily clear these to ensure the file path is tried
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)

        with patch("shared_memory.embeddings.os.path.exists", return_value=True):
            with patch(
                "builtins.open", MagicMock(side_effect=Exception("Corrupted JSON!"))
            ):
                client = embeddings.get_gemini_client()
                assert client is None
