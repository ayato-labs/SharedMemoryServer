from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import ISearchRepository


class SearchRepository(BaseSQLiteRepository, ISearchRepository):
    async def perform_fts_search(
        self,
        fts_table: str,
        id_col: str,
        content_col: str,
        title_col: str,
        fts_query: str,
    ) -> list[dict[str, Any]]:
        from ripen.common.utils import get_logger
        log = get_logger("repos.search")
        log.debug(f"QUERY: FTS search on {fts_table} for query='{fts_query}'")
        cursor = await self.conn.execute(
            f"SELECT {id_col}, {content_col}, {title_col}, bm25({fts_table}) "
            f"FROM {fts_table} WHERE {fts_table} MATCH ?",
            (fts_query,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def perform_like_search(
        self, table: str, id_col: str, content_col: str, query: str
    ) -> list[dict[str, Any]]:
        from ripen.common.utils import get_logger
        log = get_logger("repos.search")
        log.debug(f"QUERY: LIKE search on {table} for query='{query}'")
        cursor = await self.conn.execute(
            f"SELECT {id_col}, {content_col} FROM {table} "
            f"WHERE ({content_col} LIKE ? OR {id_col} LIKE ?)",
            (f"%{query}%", f"%{query}%"),
        )
        return [dict(r) for r in await cursor.fetchall()]
