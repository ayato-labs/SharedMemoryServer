from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IEntityRepository


class EntityRepository(BaseSQLiteRepository, IEntityRepository):
    async def get_all_entity_names(self) -> list[str]:
        cursor = await self.conn.execute("SELECT name FROM entities")
        return [r[0] for r in await cursor.fetchall()]

    async def get_entity_details(self, name: str) -> dict | None:
        cursor = await self.conn.execute(
            "SELECT entity_type, description FROM entities WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        importance: int,
        agent_id: str,
    ) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO entities (name, entity_type, description, "
            "importance, updated_by) VALUES (?, ?, ?, ?, ?)",
            (name, entity_type, description, importance, agent_id),
        )

    async def increment_importance(self, name: str) -> None:
        await self.conn.execute(
            "UPDATE entities SET importance = MIN(importance + 1, 10), "
            "updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (name,),
        )

    async def get_entities_by_names(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"SELECT * FROM entities WHERE name IN ({placeholders}) AND status = 'active'", names
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_status(self, names: str | list[str], status: str) -> int:
        if isinstance(names, str):
            names = [names]
        if not names:
            return 0
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            "UPDATE entities SET status = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE name IN ({placeholders})",
            [status, *names],
        )
        return cursor.rowcount

    async def get_inactive_entities(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM entities WHERE status != 'active'")
        return [dict(r) for r in await cursor.fetchall()]
