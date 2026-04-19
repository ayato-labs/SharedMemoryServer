import aiosqlite

from shared_memory.database import async_get_connection, retry_on_db_lock
from shared_memory.exceptions import DatabaseError
from shared_memory.utils import get_logger

logger = get_logger("lifecycle")


@retry_on_db_lock()
async def manage_knowledge_activation_logic(ids: list[str], status: str):
    """
    Toggles the activation status of entities, relations, observations, and bank files.
    Valid statuses: 'active', 'inactive', 'archived'
    """
    if status not in ["active", "inactive", "archived"]:
        return f"Error: Invalid status '{status}'. Must be active, inactive, or archived."

    async with await async_get_connection() as conn:
        tables = ["entities", "relations", "observations", "bank_files"]
        changes = 0

        try:
            for table in tables:
                id_col = (
                    "name" if table == "entities" else "filename" if table == "bank_files" else "id"
                )

                if table in ["relations", "observations"] and all(isinstance(i, str) for i in ids):
                    # If IDs are entity names, deactivate all related items
                    if table == "observations":
                        placeholders = ",".join(["?"] * len(ids))
                        cursor = await conn.execute(
                            f"UPDATE {table} SET status = ? WHERE entity_name IN ({placeholders})",
                            [status] + ids,
                        )
                        changes += cursor.rowcount
                    else:  # relations
                        placeholders = ",".join(["?"] * len(ids))
                        cursor = await conn.execute(
                            f"UPDATE {table} SET status = ? "
                            f"WHERE subject IN ({placeholders}) "
                            f"OR object IN ({placeholders})",
                            [status] + ids + ids,
                        )
                        changes += cursor.rowcount
                else:
                    placeholders = ",".join(["?"] * len(ids))
                    query = f"UPDATE {table} SET status = ? WHERE {id_col} IN ({placeholders})"
                    cursor = await conn.execute(query, [status] + ids)
                    changes += cursor.rowcount

            await conn.commit()
            return f"Success: Updated {changes} items across core tables to status '{status}'."
        except (aiosqlite.OperationalError, aiosqlite.Error, DatabaseError):
            await conn.rollback()
            raise  # Let the retry decorator handle it
        except Exception as e:
            await conn.rollback()
            return f"Error: Failed to update status: {e}"


@retry_on_db_lock()
async def list_inactive_knowledge_logic():
    """
    Lists all knowledge assets that are NOT active.
    """
    async with await async_get_connection() as conn:
        results = {
            "entities": [],
            "relations": [],
            "observations": [],
            "bank_files": [],
        }

        # Entities
        cursor = await conn.execute(
            "SELECT name, entity_type, status FROM entities WHERE status != 'active'"
        )
        results["entities"] = [dict(row) for row in await cursor.fetchall()]

        # Relations
        cursor = await conn.execute(
            "SELECT subject, predicate, object, status FROM relations WHERE status != 'active'"
        )
        results["relations"] = [dict(row) for row in await cursor.fetchall()]

        # Observations
        cursor = await conn.execute(
            "SELECT id, entity_name, content, status FROM observations WHERE status != 'active'"
        )
        results["observations"] = [dict(row) for row in await cursor.fetchall()]

        # Bank Files
        cursor = await conn.execute(
            "SELECT filename, status FROM bank_files WHERE status != 'active'"
        )
        results["bank_files"] = [dict(row) for row in await cursor.fetchall()]

        return results


@retry_on_db_lock()
async def run_knowledge_gc_logic(age_days: int = 180, dry_run: bool = False):
    """
    Automated Garbage Collection: Move stale active knowledge to inactive.
    Criteria:
    1. Not accessed for > age_days
    2. Stability/Importance score < 0.1
    """
    async with await async_get_connection() as conn:
        # Get metadata for stale items
        cursor = await conn.execute(
            "SELECT content_id FROM knowledge_metadata WHERE "
            "julianday('now') - julianday(last_accessed) > ? "
            "AND importance_score < 0.1",
            (age_days,),
        )
        stale_ids = [r[0] for r in await cursor.fetchall()]

        if not stale_ids:
            return "No stale knowledge found for GC."

        if dry_run:
            return (
                f"Dry Run: Found {len(stale_ids)} items as candidates "
                f"for deactivation: {stale_ids[:5]}..."
            )

        res = await manage_knowledge_activation_logic(stale_ids, "inactive")
        return f"GC Complete: {res}"
