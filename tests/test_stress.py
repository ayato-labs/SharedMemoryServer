import asyncio
import os

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import save_memory_core as save_memory
from shared_memory.utils import get_bank_dir


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_extreme_stress_100_agents(mock_gemini):
    """
    Simulate 100 concurrent agents writing to both DB and Bank.
    Verifies GlobalLock (cross-process safety) and SQLite WAL robustness.
    """
    num_agents = 100
    tasks = []

    for i in range(num_agents):
        # Alternate between many files and shared files
        filename = "stress_log.md" if i % 2 == 0 else f"agent_{i}.md"
        entities = [{"name": f"StressEntity_{i}", "description": f"Agent {i} load"}]
        bank_files = {filename: f"# Content from Agent {i}\nTimestamp: {i}"}
        tasks.append(
            save_memory(entities=entities, bank_files=bank_files, agent_id=f"agent_{i}")
        )

    # Execute 100 tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Analyze results
    success_count = 0
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(r)
        elif "Saved" in r or "Updated" in r:
            success_count += 1
        else:
            errors.append(f"Unexpected result: {r}")

    assert len(errors) == 0, (
        f"Encountered {len(errors)} errors during stress test: {errors[:5]}"
    )
    assert success_count == num_agents

    # Verify DB consistency
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM entities WHERE name LIKE 'StressEntity_%'"
        )
        row = await cursor.fetchone()
        assert row[0] == num_agents


@pytest.mark.asyncio
async def test_path_traversal_protection(mock_gemini):
    """
    Verify that malicious filenames are sanitized and don't escape the bank dir.
    """
    malicious_files = {
        "../../evil.txt": "should be sanitized",
        "nested/dir/file.md": "should be flattened",
        "CON": "reserved name on windows",
    }

    # We expect these to be sanitized without raising SecurityError
    # (SecurityError is only for absolute/rooted path traversal that escapes base_dir)
    await save_memory(bank_files=malicious_files)

    bank_dir = get_bank_dir()
    # Check that file exists but under sanitized name
    # ../../evil.txt -> evil.md
    assert os.path.exists(os.path.join(bank_dir, "evil.md"))
    assert os.path.exists(os.path.join(bank_dir, "file.md"))
    assert os.path.exists(os.path.join(bank_dir, "evil.md"))
    # nested/dir/file.md -> file.md
    assert os.path.exists(os.path.join(bank_dir, "file.md"))

    # Verify NO file was created outside bank_dir
    parent_of_bank = os.path.dirname(bank_dir)
    grandparent = os.path.dirname(parent_of_bank)
    evil_path = os.path.join(grandparent, "evil.txt")
    assert not os.path.exists(evil_path)
