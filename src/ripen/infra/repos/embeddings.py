import json

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IEmbeddingRepository


class EmbeddingRepository(BaseSQLiteRepository, IEmbeddingRepository):
    async def upsert_embedding(self, content_id: str, vector: list[float], model_name: str) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
            (content_id, json.dumps(vector).encode("utf-8"), model_name),
        )

    async def get_cached_embedding(self, content_hash: str, model_name: str) -> list[float] | None:
        cursor = await self.conn.execute(
            "SELECT vector FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
            (content_hash, model_name),
        )
        row = await cursor.fetchone()
        return json.loads(row[0]) if row else None

    async def insert_cache_entry(
        self, content_hash: str, vector: list[float], model_name: str
    ) -> None:
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO embedding_cache (content_hash, vector, model_name)
            VALUES (?, ?, ?)
            """,
            (content_hash, json.dumps(vector), model_name),
        )

    async def get_all_embeddings(self) -> list[tuple[str, bytes]]:
        cursor = await self.conn.execute("""
            SELECT e.content_id, e.vector
            FROM embeddings e
            LEFT JOIN entities ent ON e.content_id = ent.name
            LEFT JOIN bank_files bf ON e.content_id = bf.filename
            WHERE (ent.status = 'active' OR bf.status = 'active')
        """)
        return await cursor.fetchall()
