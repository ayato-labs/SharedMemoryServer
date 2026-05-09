import json

from ripen.infra.database import async_get_connection


class BankRepository:
    """Repository for managing bank_files and related queries."""
    
    @staticmethod
    async def get_active_filenames() -> list[str]:
        async with await async_get_connection() as conn:
            cursor = await conn.execute("SELECT filename FROM bank_files WHERE status = 'active'")
            return [r[0] for r in await cursor.fetchall()]

    @staticmethod
    async def get_active_files_content() -> list[tuple[str, str]]:
        async with await async_get_connection() as conn:
            cursor = await conn.execute("SELECT filename, content FROM bank_files WHERE status = 'active'")
            return await cursor.fetchall()

    @staticmethod
    async def get_all_files_content(conn) -> list[tuple[str, str]]:
        cursor = await conn.execute("SELECT filename, content FROM bank_files")
        return await cursor.fetchall()

    @staticmethod
    async def get_file_content(conn, filename: str) -> str | None:
        cursor = await conn.execute("SELECT content FROM bank_files WHERE filename = ?", (filename,))
        row = await cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    async def upsert_bank_file(conn, filename: str, content: str, agent_id: str):
        await conn.execute(
            "INSERT OR REPLACE INTO bank_files (filename, content, updated_by) VALUES (?, ?, ?)",
            (filename, content, agent_id),
        )

class AuditRepository:
    """Repository for managing audit logs."""
    
    @staticmethod
    async def log_action(conn, table_name: str, content_id: str, action: str, old_data: str | None, new_data: str, agent_id: str, meta_data: str | None = None):
        if meta_data:
            await conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id, meta_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (table_name, content_id, action, old_data, new_data, agent_id, meta_data),
            )
        else:
            await conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                (table_name, content_id, action, old_data, new_data, agent_id),
            )

class EntityRepository:
    """Repository for managing entities."""
    
    @staticmethod
    async def get_all_entity_names(conn) -> list[str]:
        cursor = await conn.execute("SELECT name FROM entities")
        return [r[0] for r in await cursor.fetchall()]

    @staticmethod
    async def get_entity_details(conn, name: str) -> dict | None:
        cursor = await conn.execute("SELECT entity_type, description FROM entities WHERE name = ?", (name,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def upsert_entity(conn, name: str, entity_type: str, description: str, importance: int, agent_id: str):
        await conn.execute(
            "INSERT OR REPLACE INTO entities (name, entity_type, description, importance, updated_by) VALUES (?, ?, ?, ?, ?)",
            (name, entity_type, description, importance, agent_id),
        )

    @staticmethod
    async def increment_importance(conn, name: str):
        await conn.execute(
            "UPDATE entities SET importance = MIN(importance + 1, 10), updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (name,),
        )

class RelationRepository:
    """Repository for managing relations."""
    
    @staticmethod
    async def upsert_relation(conn, subject: str, object_name: str, predicate: str, agent_id: str):
        await conn.execute(
            "INSERT OR REPLACE INTO relations (subject, object, predicate, created_by) VALUES (?, ?, ?, ?)",
            (subject, object_name, predicate, agent_id),
        )

    @staticmethod
    async def upsert_relations_bulk(conn, relations: list[tuple[str, str, str, str]]):
        await conn.executemany(
            "INSERT OR REPLACE INTO relations (subject, object, predicate, created_by) VALUES (?, ?, ?, ?)",
            relations,
        )

class ObservationRepository:
    """Repository for managing observations."""
    
    @staticmethod
    async def get_recent_observations(conn, entity_name: str, limit: int = 5) -> list[str]:
        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name = ? ORDER BY timestamp DESC LIMIT ?",
            (entity_name, limit)
        )
        return [row[0] for row in await cursor.fetchall()]

    @staticmethod
    async def insert_observation(conn, entity_name: str, content: str, agent_id: str):
        await conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            (entity_name, content, agent_id),
        )

class ConflictRepository:
    """Repository for managing conflicts."""
    
    @staticmethod
    async def insert_conflict(conn, entity_name: str, existing_content: str, new_content: str, reason: str, agent_id: str):
        await conn.execute(
            "INSERT INTO conflicts (entity_name, existing_content, new_content, reason, agent_id) VALUES (?, ?, ?, ?, ?)",
            (entity_name, existing_content, new_content, reason, agent_id),
        )

class EmbeddingRepository:
    """Repository for managing embeddings."""
    
    @staticmethod
    async def upsert_embedding(conn, content_id: str, vector: list[float], model_name: str):
        await conn.execute(
            "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
            (content_id, json.dumps(vector).encode("utf-8"), model_name),
        )

class TroubleshootingRepository:
    """Repository for managing troubleshooting knowledge."""
    
    @staticmethod
    async def insert_troubleshooting(conn, title: str, solution: str, affected_functions: str, env_metadata: str):
        await conn.execute(
            """
            INSERT INTO troubleshooting_knowledge (title, solution, affected_functions, env_metadata)
            VALUES (?, ?, ?, ?)
            """,
            (title, solution, affected_functions, env_metadata),
        )

class TagRepository:
    """Repository for managing tags."""
    
    @staticmethod
    async def replace_tags(conn, content_id: str, content_type: str, tags: list[str]):
        await conn.execute(
            "DELETE FROM tags WHERE content_id = ? AND content_type = ?", (content_id, content_type)
        )
        data = [(t, content_id, content_type) for t in tags]
        await conn.executemany(
            "INSERT OR IGNORE INTO tags (tag, content_id, content_type) VALUES (?, ?, ?)", data
        )

    @staticmethod
    async def get_content_ids_by_tags(conn, tags: list[str]) -> list[str]:
        placeholders = ",".join(["?"] * len(tags))
        cursor = await conn.execute(
            f"SELECT DISTINCT content_id FROM tags WHERE tag IN ({placeholders})", tags
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

class GraphRepository:
    """Repository for retrieving complete graph segments."""

    @staticmethod
    async def get_full_graph(conn):
        cursor = await conn.execute("SELECT * FROM entities WHERE status = 'active'")
        entities = await cursor.fetchall()
        cursor = await conn.execute("SELECT * FROM relations WHERE status = 'active'")
        relations = await cursor.fetchall()
        cursor = await conn.execute("SELECT * FROM observations WHERE status = 'active'")
        observations = await cursor.fetchall()
        return entities, relations, observations

    @staticmethod
    async def search_graph(conn, query: str):
        cursor = await conn.execute(
            "SELECT * FROM entities WHERE "
            "(name LIKE ? OR description LIKE ? OR entity_type LIKE ?) AND status = 'active'",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
        matched_entities = await cursor.fetchall()
        entity_matched_names = [e["name"] for e in matched_entities]

        cursor = await conn.execute(
            "SELECT * FROM observations WHERE content LIKE ? AND status = 'active'",
            (f"%{query}%",),
        )
        direct_observations = await cursor.fetchall()
        obs_matched_entity_names = list(set([o["entity_name"] for o in direct_observations]))

        all_matched_names = list(set(entity_matched_names + obs_matched_entity_names))

        if not all_matched_names:
            return [], [], [], []

        placeholders = ",".join(["?"] * len(all_matched_names))
        cursor = await conn.execute(
            f"SELECT * FROM relations WHERE (subject IN ({placeholders}) "
            f"OR object IN ({placeholders})) AND status = 'active'",
            all_matched_names + all_matched_names,
        )
        relations = await cursor.fetchall()

        cursor = await conn.execute(
            "SELECT * FROM observations WHERE entity_name IN "
            f"({placeholders}) AND status = 'active'",
            all_matched_names,
        )
        linked_observations = await cursor.fetchall()
        
        return matched_entities, relations, direct_observations, linked_observations
