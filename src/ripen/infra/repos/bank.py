from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IBankRepository


class BankRepository(BaseSQLiteRepository, IBankRepository):
    async def get_active_filenames(self) -> list[str]:
        cursor = await self.conn.execute("SELECT filename FROM bank_files WHERE status = 'active'")
        return [r[0] for r in await cursor.fetchall()]

    async def get_active_files_content(self) -> list[tuple[str, str]]:
        cursor = await self.conn.execute(
            "SELECT filename, content FROM bank_files WHERE status = 'active'"
        )
        return await cursor.fetchall()

    async def get_all_files_content(self) -> list[tuple[str, str]]:
        cursor = await self.conn.execute("SELECT filename, content FROM bank_files")
        return await cursor.fetchall()

    async def get_file_content(self, filename: str) -> str | None:
        cursor = await self.conn.execute(
            "SELECT content FROM bank_files WHERE filename = ?", (filename,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def upsert_bank_file(self, filename: str, content: str, agent_id: str) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO bank_files (filename, content, updated_by) VALUES (?, ?, ?)",
            (filename, content, agent_id),
        )

    async def get_bank_files_by_names(self, names: list[str]) -> list[tuple[str, str]]:
        if not names:
            return []
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"SELECT filename, content FROM bank_files WHERE filename IN ({placeholders}) "
            "AND status = 'active'",
            names,
        )
        return await cursor.fetchall()

    async def update_status(self, filenames: str | list[str], status: str) -> int:
        if isinstance(filenames, str):
            filenames = [filenames]
        if not filenames:
            return 0
        placeholders = ",".join(["?"] * len(filenames))
        cursor = await self.conn.execute(
            "UPDATE bank_files SET status = ?, last_synced = CURRENT_TIMESTAMP "
            f"WHERE filename IN ({placeholders})",
            [status, *filenames],
        )
        return cursor.rowcount

    async def get_inactive_bank_files(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM bank_files WHERE status != 'active'")
        return [dict(r) for r in await cursor.fetchall()]
