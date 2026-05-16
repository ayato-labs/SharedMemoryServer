from datetime import UTC, datetime, timedelta

import pytest

from ripen.ops.lifecycle import run_knowledge_gc_logic

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_run_knowledge_gc_logic_stale_items(db_conn):
    """Verify GC correctly identifies and deactivates stale items."""
    # 1. Setup stale item (last accessed 200 days ago)
    stale_id = "stale_entity"
    stale_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()

    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        (stale_id, "test", "stale info", "active"),
    )
    await db_conn.execute(
        "INSERT INTO knowledge_metadata (content_id, access_count, last_accessed) VALUES (?, ?, ?)",
        (stale_id, 1, stale_date),
    )

    # 2. Setup fresh item
    fresh_id = "fresh_entity"
    fresh_date = datetime.now(UTC).isoformat()
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        (fresh_id, "test", "fresh info", "active"),
    )
    await db_conn.execute(
        "INSERT INTO knowledge_metadata (content_id, access_count, last_accessed) VALUES (?, ?, ?)",
        (fresh_id, 1, fresh_date),
    )

    await db_conn.commit()

    # 3. Run GC
    res = await run_knowledge_gc_logic(age_days=180, dry_run=False)
    assert "GC Complete" in res

    # 4. Verify results
    cursor = await db_conn.execute("SELECT status FROM entities WHERE name = ?", (stale_id,))
    assert (await cursor.fetchone())[0] == "inactive"

    cursor = await db_conn.execute("SELECT status FROM entities WHERE name = ?", (fresh_id,))
    assert (await cursor.fetchone())[0] == "active"


@pytest.mark.asyncio
async def test_run_knowledge_gc_dry_run(db_conn):
    """Verify dry run doesn't change status."""
    stale_id = "stale_dry_run"
    stale_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        (stale_id, "test", "stale info", "active"),
    )
    await db_conn.execute(
        "INSERT INTO knowledge_metadata (content_id, access_count, last_accessed) VALUES (?, ?, ?)",
        (stale_id, 1, stale_date),
    )
    await db_conn.commit()

    res = await run_knowledge_gc_logic(age_days=180, dry_run=True)
    assert "Dry Run" in res

    cursor = await db_conn.execute("SELECT status FROM entities WHERE name = ?", (stale_id,))
    assert (await cursor.fetchone())[0] == "active"
