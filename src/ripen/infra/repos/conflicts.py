from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IConflictRepository


class ConflictRepository(BaseSQLiteRepository, IConflictRepository):
    async def insert_conflict(
        self,
        entity_name: str,
        existing_content: str,
        new_content: str,
        reason: str,
        agent_id: str,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO conflicts (entity_name, existing_content, new_content, reason, agent_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_name, existing_content, new_content, reason, agent_id),
        )

    async def get_unresolved_conflicts(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM conflicts WHERE resolved = 0")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_conflict_by_id(self, conflict_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM conflicts WHERE id = ?", (conflict_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_resolved(self, conflict_id: int) -> None:
        await self.conn.execute("UPDATE conflicts SET resolved = 1 WHERE id = ?", (conflict_id,))
