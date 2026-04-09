import json
import os

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import (
    create_snapshot_core as create_snapshot_logic,
)
from shared_memory.logic import (
    get_audit_history_core as get_audit_history_logic,
)
from shared_memory.logic import (
    get_memory_health_core as get_memory_health_logic,
)
from shared_memory.logic import (
    restore_snapshot_core as restore_snapshot_logic,
)
from shared_memory.logic import (
    rollback_memory_core as rollback_memory_logic,
)
from shared_memory.utils import get_db_path


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_snapshot_lifecycle():
    # 1. Create Snapshot
    res = await create_snapshot_logic("test_snap", "Initial backup")
    assert "Snapshot 'test_snap' created" in res

    # Verify file exists
    snapshot_dir = os.path.join(os.path.dirname(get_db_path()), "snapshots")
    assert os.path.exists(snapshot_dir)
    files = os.listdir(snapshot_dir)
    assert len(files) >= 1

    # 2. Restore Snapshot
    # Snapshot ID in DB should be 1
    res_restore = await restore_snapshot_logic(1)
    assert "Successfully restored" in res_restore


@pytest.mark.asyncio
async def test_audit_and_rollback():
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO entities (name, entity_type, description) "
            "VALUES ('X', 'concept', 'Old Dev')"
        )
        # Manually add audit log
        await conn.execute(
            "INSERT INTO audit_logs "
            "(table_name, content_id, action, old_data, new_data) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "entities",
                "X",
                "UPDATE",
                json.dumps({"name": "X", "type": "concept", "desc": "Very Old"}),
                json.dumps({"desc": "Old Dev"}),
            ),
        )
        await conn.commit()

    # Check history
    history = await get_audit_history_logic(limit=1)
    assert len(history) == 1
    audit_id = history[0]["id"]

    # Rollback
    res = await rollback_memory_logic(audit_id)
    assert "Successfully rolled back" in res

    # Verify DB state
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT description FROM entities WHERE name = 'X'")
        row = await cursor.fetchone()
        assert row[0] == "Very Old"


@pytest.mark.asyncio
async def test_memory_health(mock_gemini):
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name) VALUES ('E1'), ('E2')")
        await conn.commit()

    health = await get_memory_health_logic()
    assert health["management_stats"]["entities_count"] == 2
    assert "gaps_analysis" in health["management_stats"]
    assert health["components"]["api"]["status"] == "healthy"
