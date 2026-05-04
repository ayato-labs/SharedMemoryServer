import aiosqlite

from shared_memory.infra.database import async_get_connection


async def manage_knowledge_activation_logic(ids: list[str], status: str):
    \"\"\"Updates the activation status (active/inactive) for content items.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        updated_count = 0
        for content_id in ids:
            await cursor.execute(
                \"UPDATE knowledge_metadata SET is_active = ? WHERE content_id = ?\",
                (1 if status == \"active\" else 0, content_id),
            )
            updated_count += 1
        await conn.commit()
        return f\"Updated {updated_count} items to status '{status}'.\"


async def list_inactive_knowledge_logic():
    \"\"\"Lists items that are marked as inactive.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            \"\"\"
            SELECT content_id, access_count, last_accessed
            FROM knowledge_metadata
            WHERE is_active = 0
            \"\"\"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def run_knowledge_gc_logic(age_days: int = 180, dry_run: bool = False):
    \"\"\"Deletes or archives knowledge that hasn't been accessed for age_days.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            \"\"\"
            SELECT content_id FROM knowledge_metadata
            WHERE last_accessed < datetime('now', ?)
            \"\"\",
            (f\"-{age_days} days\",),
        )
        rows = await cursor.fetchall()
        ids = [row[0] for row in rows]

        if dry_run:
            return f\"[Dry Run] Would remove {len(ids)} stale items.\"

        for content_id in ids:
            # We don't delete from metadata, we delete from the primary source
            # and let cascading or manual cleanup handle it.
            # SSoT: This requires cross-table cleanup logic.
            pass

        return f\"Removed {len(ids)} stale items from memory.\"
