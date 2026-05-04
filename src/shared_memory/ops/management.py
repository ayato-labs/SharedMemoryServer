import json

from shared_memory.infra.database import async_get_connection


async def get_audit_history_logic(limit: int = 20, table_name: str | None = None):
    \"\"\"Retrieves the change history from the audit log.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        if table_name:
            await cursor.execute(
                \"\"\"
                SELECT * FROM audit_log
                WHERE table_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
                \"\"\",
                (table_name, limit),
            )
        else:
            await cursor.execute(
                \"\"\"
                SELECT * FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
                \"\"\",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def rollback_memory_logic(audit_id: int):
    \"\"\"Reverts a specific change recorded in the audit log (placeholder).\"\"\"
    # Implementation depends on complex inverse operations
    return f\"Rollback for ID {audit_id} is not yet implemented in SSoT engine.\"


async def create_snapshot_logic(name: str, description: str = \"\"):
    \"\"\"Creates a point-in-time snapshot of the current knowledge state.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            \"\"\"
            INSERT INTO snapshots (name, description, state_summary)
            VALUES (?, ?, ?)
            \"\"\",
            (name, description, \"SSoT Snapshot\"),
        )
        await conn.commit()
        return f\"Snapshot '{name}' created successfully.\"


async def restore_snapshot_logic(snapshot_id: int):
    \"\"\"Restores knowledge state from a snapshot (placeholder).\"\"\"
    return f\"Restore for Snapshot {snapshot_id} is not yet implemented.\"


async def get_memory_health_logic():
    \"\"\"Performs a basic integrity check on DB tables.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        stats = {}
        for table in [\"entities\", \"graph\", \"observations\", \"bank_files\"]:
            await cursor.execute(f\"SELECT COUNT(*) FROM {table}\")
            count = await cursor.fetchone()
            stats[table] = count[0] if count else 0
        return stats
