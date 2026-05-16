from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import ITagRepository


class TagRepository(BaseSQLiteRepository, ITagRepository):
    async def replace_tags(self, content_id: str, content_type: str, tags: list[str]) -> None:
        await self.conn.execute(
            "DELETE FROM tags WHERE content_id = ? AND content_type = ?", (content_id, content_type)
        )
        data = [(t, content_id, content_type) for t in tags]
        await self.conn.executemany(
            "INSERT OR IGNORE INTO tags (tag, content_id, content_type) VALUES (?, ?, ?)", data
        )

    async def get_content_ids_by_tags(self, tags: list[str]) -> list[str]:
        if not tags:
            return []
        placeholders = ",".join(["?"] * len(tags))
        cursor = await self.conn.execute(
            f"SELECT DISTINCT content_id FROM tags WHERE tag IN ({placeholders})", tags
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def search_tags(self, query_words: list[str]) -> list[dict[str, Any]]:
        if not query_words:
            return []
        placeholders = ",".join(["?"] * len(query_words))
        cursor = await self.conn.execute(
            f"SELECT content_id, content_type, tag FROM tags WHERE tag IN ({placeholders})",
            [f"#{w}" for w in query_words],
        )
        return [dict(r) for r in await cursor.fetchall()]
