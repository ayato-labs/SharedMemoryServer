from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import ITroubleshootingRepository


class TroubleshootingRepository(BaseSQLiteRepository, ITroubleshootingRepository):
    async def insert_troubleshooting(
        self, title: str, solution: str, affected_functions: str, env_metadata: str
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO troubleshooting_knowledge 
            (title, solution, affected_functions, env_metadata)
            VALUES (?, ?, ?, ?)
            """,
            (title, solution, affected_functions, env_metadata),
        )

    async def get_troubleshooting_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        cursor = await self.conn.execute(
            f"SELECT * FROM troubleshooting_knowledge WHERE id IN ({placeholders})", ids
        )
        return [dict(r) for r in await cursor.fetchall()]
