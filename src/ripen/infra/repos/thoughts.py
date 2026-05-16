from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IThoughtRepository


class ThoughtRepository(BaseSQLiteRepository, IThoughtRepository):
    async def init_tables(self) -> None:
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS thought_history (
                session_id TEXT,
                thought_number INTEGER,
                total_thoughts INTEGER,
                thought TEXT,
                next_thought_needed BOOLEAN,
                is_revision BOOLEAN,
                revises_thought INTEGER,
                branch_from_thought INTEGER,
                branch_id TEXT,
                agent_id TEXT,
                meta_data TEXT,
                distilled BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, thought_number)
            )
        """
        )
        # Create FTS5 table for thought search
        await self.conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS thought_history_fts "
            "USING fts5(session_id, thought_number, thought, content='thought_history')"
        )
        # Triggers for FTS
        await self.conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS thought_history_ai AFTER INSERT ON thought_history BEGIN
                INSERT INTO thought_history_fts(rowid, session_id, thought_number, thought) 
                VALUES (new.rowid, new.session_id, new.thought_number, new.thought);
            END;
        """
        )

    async def insert_thought(
        self,
        session_id: str,
        thought_number: int,
        total_thoughts: int,
        thought: str,
        next_thought_needed: bool,
        is_revision: bool,
        revises_thought: int | None,
        branch_from_thought: int | None,
        branch_id: str | None,
        agent_id: str,
        meta_data: str | None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO thought_history (
                session_id, thought_number, total_thoughts, thought,
                next_thought_needed, is_revision, revises_thought,
                branch_from_thought, branch_id, agent_id, meta_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                thought_number,
                total_thoughts,
                thought,
                1 if next_thought_needed else 0,
                1 if is_revision else 0,
                revises_thought,
                branch_from_thought,
                branch_id,
                agent_id,
                meta_data,
            ),
        )

    async def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT * FROM thought_history WHERE session_id = ? ORDER BY thought_number ASC",
            (session_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def mark_session_distilled(self, session_id: str) -> None:
        await self.conn.execute(
            "UPDATE thought_history SET distilled = 1 WHERE session_id = ?",
            (session_id,),
        )

    async def get_undistilled_sessions(self) -> list[str]:
        cursor = await self.conn.execute(
            "SELECT DISTINCT session_id FROM thought_history WHERE distilled = 0"
        )
        return [row[0] for row in await cursor.fetchall()]

    async def get_total_thought_count(self) -> int:
        cursor = await self.conn.execute("SELECT COUNT(*) FROM thought_history")
        row = await cursor.fetchone()
        return row[0] or 0

    async def get_total_session_count(self) -> int:
        cursor = await self.conn.execute("SELECT COUNT(DISTINCT session_id) FROM thought_history")
        row = await cursor.fetchone()
        return row[0] or 0

    async def search_thoughts(
        self, fts_query: str, exclude_session_id: str
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT session_id, thought_number, thought, bm25(thought_history_fts) "
            "FROM thought_history_fts WHERE thought_history_fts MATCH ? "
            "AND session_id != ?",
            (fts_query, exclude_session_id),
        )
        return [dict(row) for row in await cursor.fetchall()]
