import asyncio

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import save_memory_core as save_memory


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_high_concurrency_writes(mock_gemini):
    """
    Simulate multiple agents hitting save_memory at the exact same time.
    Verifies that our locking and busy_timeout prevent failures.
    """
    num_agents = 5  # Targeted concurrency limit for personal use/small teams
    tasks = []

    for i in range(num_agents):
        entities = [{"name": f"AgentEntity_{i}", "description": f"Saved by agent {i}"}]
        bank_files = {f"agent_{i}.md": f"# Agent {i} Content"}
        # Launch concurrently
        tasks.append(
            save_memory(entities=entities, bank_files=bank_files, agent_id=f"agent_{i}")
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for any exceptions
    for r in results:
        if isinstance(r, Exception):
            pytest.fail(f"Concurrency task failed with exception: {r}")
        assert "Saved" in r or "Updated" in r

    # Verify Database Consistency
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM entities WHERE name LIKE 'AgentEntity_%'"
        )
        count = (await cursor.fetchone())[0]
        assert count == num_agents

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM bank_files WHERE filename LIKE 'agent_%.md'"
        )
        bank_count = (await cursor.fetchone())[0]
        assert bank_count == num_agents


@pytest.mark.asyncio
async def test_mixed_read_write_concurrency(mock_gemini):
    """
    Verify that WAL mode allows reading while writing.
    """
    from shared_memory.bank import read_bank_data

    # 1. Start a slow write
    write_task = save_memory(
        entities=[{"name": "WriteLoad", "description": "heavy load"}],
        bank_files={"load.md": "content" * 1000},
    )

    # 2. Start a read
    read_task = read_bank_data()

    results = await asyncio.gather(write_task, read_task)

    assert "Saved" in results[0]
    assert isinstance(results[1], dict)
