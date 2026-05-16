from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IObservationRepository


class ObservationRepository(BaseSQLiteRepository, IObservationRepository):
    async def get_recent_observations(self, entity_name: str, limit: int = 5) -> list[str]:
        from ripen.common.utils import get_logger
        log = get_logger("repos.obs")
        log.debug(f"QUERY: get_recent_observations for {entity_name} (limit={limit})")
        cursor = await self.conn.execute(
            "SELECT content FROM observations WHERE entity_name = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (entity_name, limit),
        )
        return [row[0] for row in await cursor.fetchall()]

    async def insert_observation(self, entity_name: str, content: str, agent_id: str) -> None:
        from ripen.common.utils import get_logger
        log = get_logger("repos.obs")
        log.debug(f"QUERY: insert_observation for {entity_name} (agent={agent_id})")
        await self.conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            (entity_name, content, agent_id),
        )

    async def get_observations_by_entity_names(self, names: list[str]) -> list[dict[str, Any]]:
        from ripen.common.utils import get_logger
        log = get_logger("repos.obs")
        log.debug(f"QUERY: get_observations_by_entity_names for {len(names)} entities")
        if not names:
            return []
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"SELECT * FROM observations WHERE entity_name IN ({placeholders}) "
            "AND status = 'active'",
            names,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_active_observations_by_entity(self, entity_name: str) -> list[tuple[str, str]]:
        cursor = await self.conn.execute(
            "SELECT content, timestamp FROM observations WHERE entity_name = ? AND status='active'",
            (entity_name,),
        )
        return await cursor.fetchall()

    async def update_status(self, obs_id: int, status: str) -> None:
        await self.conn.execute(
            "UPDATE observations SET status = ? WHERE id = ?",
            (status, obs_id),
        )

    async def update_status_by_entities(self, names: list[str], status: str) -> int:
        if not names:
            return 0
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"UPDATE observations SET status = ? WHERE entity_name IN ({placeholders})",
            [status, *names],
        )
        return cursor.rowcount

    async def get_inactive_observations(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM observations WHERE status != 'active'")
        return [dict(r) for r in await cursor.fetchall()]
