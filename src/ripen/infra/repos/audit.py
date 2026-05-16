from typing import Any

from ripen.infra.repos.base import BaseSQLiteRepository
from ripen.infra.repository_base import IAuditRepository


class AuditRepository(BaseSQLiteRepository, IAuditRepository):
    async def log_action(
        self,
        table_name: str,
        content_id: str,
        action: str,
        old_data: str | None,
        new_data: str,
        agent_id: str,
        meta_data: str | None = None,
    ) -> None:
        if meta_data:
            await self.conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, old_data, "
                "new_data, agent_id, meta_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (table_name, content_id, action, old_data, new_data, agent_id, meta_data),
            )
        else:
            await self.conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, old_data, "
                "new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                (table_name, content_id, action, old_data, new_data, agent_id),
            )

    async def get_history(self, limit: int, table_name: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM audit_logs "
        params = []
        if table_name:
            query += "WHERE table_name = ? "
            params.append(table_name)
        query += "ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await self.conn.execute(query, tuple(params))
        return [dict(r) for r in await cursor.fetchall()]

    async def get_audit_log_by_id(self, audit_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM audit_logs WHERE id = ?", (audit_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
