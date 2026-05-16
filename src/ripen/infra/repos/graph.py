from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IGraphRepository


class GraphRepository(BaseSQLiteRepository, IGraphRepository):
    async def get_full_graph(self, limit: int = 100) -> tuple[list[dict], list[dict], list[dict]]:
        cursor = await self.conn.execute(
            "SELECT * FROM entities WHERE status = 'active' LIMIT ?", (limit,)
        )
        entities = [dict(r) for r in await cursor.fetchall()]

        cursor = await self.conn.execute(
            "SELECT * FROM relations WHERE status = 'active' LIMIT ?", (limit,)
        )
        relations = [dict(r) for r in await cursor.fetchall()]

        cursor = await self.conn.execute(
            "SELECT * FROM observations WHERE status = 'active' ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        observations = [dict(r) for r in await cursor.fetchall()]
        return entities, relations, observations

    async def search_graph(
        self, query: str
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        cursor = await self.conn.execute(
            "SELECT * FROM entities WHERE "
            "(name LIKE ? OR description LIKE ? OR entity_type LIKE ?) AND status = 'active'",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
        matched_entities = [dict(r) for r in await cursor.fetchall()]
        entity_matched_names = [e["name"] for e in matched_entities]

        cursor = await self.conn.execute(
            "SELECT * FROM observations WHERE content LIKE ? AND status = 'active'",
            (f"%{query}%",),
        )
        direct_observations = [dict(r) for r in await cursor.fetchall()]
        obs_matched_entity_names = list(set([o["entity_name"] for o in direct_observations]))

        all_matched_names = list(set(entity_matched_names + obs_matched_entity_names))

        if not all_matched_names:
            return [], [], [], []

        placeholders = ",".join(["?"] * len(all_matched_names))
        cursor = await self.conn.execute(
            f"SELECT * FROM relations WHERE (subject IN ({placeholders}) "
            f"OR object IN ({placeholders})) AND status = 'active'",
            all_matched_names + all_matched_names,
        )
        relations = [dict(r) for r in await cursor.fetchall()]

        cursor = await self.conn.execute(
            "SELECT * FROM observations WHERE entity_name IN "
            f"({placeholders}) AND status = 'active'",
            all_matched_names,
        )
        linked_observations = [dict(r) for r in await cursor.fetchall()]

        return matched_entities, relations, direct_observations, linked_observations
