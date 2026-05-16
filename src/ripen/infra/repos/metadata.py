import json
from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IMetadataRepository


class MetadataRepository(BaseSQLiteRepository, IMetadataRepository):
    async def get_all_metadata(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_access(self, content_id: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO knowledge_metadata (
                content_id, access_count, last_accessed,
                importance_score, stability, decay_rate
            )
            VALUES (?, 1, CURRENT_TIMESTAMP, 1.0, 1.1, 0.01)
            ON CONFLICT(content_id) DO UPDATE SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP,
                stability = stability * 1.1
            """,
            (content_id,),
        )

    async def get_access_stats_summary(self) -> dict[str, Any]:
        cursor = await self.conn.execute(
            "SELECT SUM(access_count), COUNT(*) FROM knowledge_metadata"
        )
        row = await cursor.fetchone()
        return {"total_access": row[0] or 0, "accessed_units": row[1] or 0}

    async def get_successful_search_stats(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT results_count, hit_content_ids, avg_similarity, timestamp "
            "FROM search_stats WHERE results_count > 0"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_total_search_count(self) -> int:
        cursor = await self.conn.execute("SELECT COUNT(*) FROM search_stats")
        row = await cursor.fetchone()
        return row[0] or 0

    async def log_search_stat(
        self, query: str, results_count: int, hit_ids: list[str], avg_sim: float = 0.0
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO search_stats (
                query, results_count, hit_content_ids, avg_similarity
            ) VALUES (?, ?, ?, ?)
            """,
            (query, results_count, json.dumps(hit_ids), avg_sim),
        )
