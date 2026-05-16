from typing import Any

from loguru import logger

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IManagementRepository


class ManagementRepository(BaseSQLiteRepository, IManagementRepository):
    async def get_table_info(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in await cursor.fetchall()]
        results = []
        for table in tables:
            try:
                c = await self.conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = (await c.fetchone())[0]
                results.append({"name": table, "count": count})
            except Exception as e:
                logger.warning(f"Failed to get count for table {table}: {e}")
                continue
        return results

    async def vacuum_into(self, target_path: str) -> None:
        await self.conn.execute(f"VACUUM INTO '{target_path}'")

    async def delete_stale_knowledge(self, age_days: int) -> int:
        # Mark as inactive instead of deleting for safety
        await self.conn.execute(
            """
            UPDATE entities SET status = 'inactive'
            WHERE importance < 3 
            AND created_at < date('now', ?)
            """,
            (f"-{age_days} days",),
        )
        return self.conn.total_changes

    async def get_count(self, table_name: str) -> int:
        try:
            cursor = await self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            row = await cursor.fetchone()
            return row[0] or 0
        except Exception as e:
            logger.warning(f"Failed to get count for table {table_name}: {e}")
            return 0

    async def get_creation_timestamp(self, content_id: str) -> str | None:
        query = (
            "SELECT created_at FROM entities WHERE name = ? "
            "UNION "
            "SELECT last_synced as created_at FROM bank_files WHERE filename = ?"
        )
        cursor = await self.conn.execute(query, (content_id, content_id))
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_database_stats(self) -> dict[str, Any]:
        stats = {}
        cursor = await self.conn.execute("PRAGMA page_count")
        stats["page_count"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA page_size")
        stats["page_size"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA freelist_count")
        stats["freelist_count"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA journal_mode")
        stats["journal_mode"] = (await cursor.fetchone())[0]

        stats["fragmentation_ratio"] = (
            stats["freelist_count"] / stats["page_count"] if stats["page_count"] > 0 else 0
        )
        stats["wal_mode"] = stats["journal_mode"].lower() == "wal"
        return stats

    async def get_embedding_model_distribution(self) -> dict[str, int]:
        cursor = await self.conn.execute(
            "SELECT model_name, COUNT(*) FROM embeddings GROUP BY model_name"
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def get_isolated_entities(self) -> list[str]:
        # Entities not present in relations as subject or object
        query = """
            SELECT name FROM entities 
            WHERE status = 'active'
            AND name NOT IN (SELECT DISTINCT subject FROM relations WHERE status = 'active')
            AND name NOT IN (SELECT DISTINCT object FROM relations WHERE status = 'active')
        """
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_entity_type_distribution(self) -> dict[str, int]:
        cursor = await self.conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities "
            "WHERE status = 'active' GROUP BY entity_type"
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def get_agent_contribution_stats(self) -> dict[str, int]:
        # Aggregating from entities and observations
        query = """
            SELECT created_by, COUNT(*) FROM (
                SELECT created_by FROM entities
                UNION ALL
                SELECT created_by FROM observations
            ) GROUP BY created_by
        """
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return {r[0] or "unknown": r[1] for r in rows}

    async def get_snapshot_path(self, snapshot_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def insert_snapshot(self, name: str, description: str, file_path: str) -> None:
        await self.conn.execute(
            "INSERT INTO snapshots (name, description, file_path) VALUES (?, ?, ?)",
            (name, description, file_path),
        )

    async def list_snapshots(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT id, name, timestamp FROM snapshots ORDER BY timestamp DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def optimize_database(self) -> None:
        await self.conn.execute("PRAGMA optimize")
        await self.conn.execute("ANALYZE")

    async def get_low_activity_ids(self, before_date: str, max_access_count: int) -> list[str]:
        """Identify IDs of knowledge items that have low activity based on access count and date."""
        query = """
            SELECT content_id FROM knowledge_metadata 
            WHERE last_accessed < ? AND access_count <= ?
        """
        cursor = await self.conn.execute(query, (before_date, max_access_count))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
