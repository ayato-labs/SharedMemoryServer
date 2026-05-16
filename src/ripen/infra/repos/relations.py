from collections.abc import Sequence
from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IRelationRepository


class RelationRepository(BaseSQLiteRepository, IRelationRepository):
    async def upsert_relation(
        self, subject: str, object_name: str, predicate: str, agent_id: str
    ) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO relations (subject, object, predicate, created_by) "
            "VALUES (?, ?, ?, ?)",
            (subject, object_name, predicate, agent_id),
        )

    async def upsert_relations_bulk(self, relations: Sequence[tuple[str, str, str, str]]) -> None:
        await self.conn.executemany(
            "INSERT OR REPLACE INTO relations (subject, object, predicate, created_by) "
            "VALUES (?, ?, ?, ?)",
            relations,
        )

    async def get_relations_by_subjects_or_objects(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"SELECT * FROM relations WHERE (subject IN ({placeholders}) "
            f"OR object IN ({placeholders})) AND status = 'active'",
            names + names,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_relations_by_entity(self, entity_name: str) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT * FROM relations WHERE (subject = ? OR object = ?) AND status='active'",
            (entity_name, entity_name),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_status(self, subject: str, object: str, predicate: str, status: str) -> None:
        await self.conn.execute(
            "UPDATE relations SET status = ? WHERE subject = ? AND object = ? AND predicate = ?",
            (status, subject, object, predicate),
        )

    async def update_status_by_entities(self, names: list[str], status: str) -> int:
        if not names:
            return 0
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            "UPDATE relations SET status = ? "
            f"WHERE subject IN ({placeholders}) OR object IN ({placeholders})",
            [status, *names, *names],
        )
        return cursor.rowcount

    async def get_inactive_relations(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM relations WHERE status != 'active'")
        return [dict(r) for r in await cursor.fetchall()]
