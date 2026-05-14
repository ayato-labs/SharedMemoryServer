import json
from collections.abc import Sequence
from typing import Any

import aiosqlite
from loguru import logger

from ripen.infra.repository_base import (
    IAuditRepository,
    IBankRepository,
    IConflictRepository,
    IEmbeddingRepository,
    IEntityRepository,
    IGraphRepository,
    IManagementRepository,
    IMetadataRepository,
    IObservationRepository,
    IRelationRepository,
    ISearchRepository,
    ITagRepository,
    IThoughtRepository,
    ITroubleshootingRepository,
)


class BaseSQLiteRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn


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


class EntityRepository(BaseSQLiteRepository, IEntityRepository):
    async def get_all_entity_names(self) -> list[str]:
        cursor = await self.conn.execute("SELECT name FROM entities")
        return [r[0] for r in await cursor.fetchall()]

    async def get_entity_details(self, name: str) -> dict | None:
        cursor = await self.conn.execute(
            "SELECT entity_type, description FROM entities WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        importance: int,
        agent_id: str,
    ) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO entities (name, entity_type, description, "
            "importance, updated_by) VALUES (?, ?, ?, ?, ?)",
            (name, entity_type, description, importance, agent_id),
        )

    async def increment_importance(self, name: str) -> None:
        await self.conn.execute(
            "UPDATE entities SET importance = MIN(importance + 1, 10), "
            "updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (name,),
        )

    async def get_entities_by_names(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            f"SELECT * FROM entities WHERE name IN ({placeholders}) AND status = 'active'", names
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_status(self, names: str | list[str], status: str) -> int:
        if isinstance(names, str):
            names = [names]
        if not names:
            return 0
        placeholders = ",".join(["?"] * len(names))
        cursor = await self.conn.execute(
            "UPDATE entities SET status = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE name IN ({placeholders})",
            [status, *names],
        )
        return cursor.rowcount

    async def get_inactive_entities(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM entities WHERE status != 'active'")
        return [dict(r) for r in await cursor.fetchall()]


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


class ObservationRepository(BaseSQLiteRepository, IObservationRepository):
    async def get_recent_observations(self, entity_name: str, limit: int = 5) -> list[str]:
        cursor = await self.conn.execute(
            "SELECT content FROM observations WHERE entity_name = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (entity_name, limit),
        )
        return [row[0] for row in await cursor.fetchall()]

    async def insert_observation(self, entity_name: str, content: str, agent_id: str) -> None:
        await self.conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            (entity_name, content, agent_id),
        )

    async def get_observations_by_entity_names(self, names: list[str]) -> list[dict[str, Any]]:
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


class ConflictRepository(BaseSQLiteRepository, IConflictRepository):
    async def insert_conflict(
        self,
        entity_name: str,
        existing_content: str,
        new_content: str,
        reason: str,
        agent_id: str,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO conflicts (entity_name, existing_content, new_content, reason, agent_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_name, existing_content, new_content, reason, agent_id),
        )

    async def get_unresolved_conflicts(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT * FROM conflicts WHERE resolved = 0")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_conflict_by_id(self, conflict_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM conflicts WHERE id = ?", (conflict_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_resolved(self, conflict_id: int) -> None:
        await self.conn.execute("UPDATE conflicts SET resolved = 1 WHERE id = ?", (conflict_id,))


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


class TroubleshootingRepository(BaseSQLiteRepository, ITroubleshootingRepository):
    async def insert_troubleshooting(
        self, title: str, solution: str, affected_functions: str, env_metadata: str
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO troubleshooting_knowledge 
            (title, solution, affected_functions, env_metadata)
            VALUES (?, ?, ?, ?)
            """,
            (title, solution, affected_functions, env_metadata),
        )

    async def get_troubleshooting_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        cursor = await self.conn.execute(
            f"SELECT * FROM troubleshooting_knowledge WHERE id IN ({placeholders})", ids
        )
        return [dict(r) for r in await cursor.fetchall()]


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


class GraphRepository(BaseSQLiteRepository, IGraphRepository):
    async def get_full_graph(self) -> tuple[list[dict], list[dict], list[dict]]:
        cursor = await self.conn.execute("SELECT * FROM entities WHERE status = 'active'")
        entities = [dict(r) for r in await cursor.fetchall()]
        cursor = await self.conn.execute("SELECT * FROM relations WHERE status = 'active'")
        relations = [dict(r) for r in await cursor.fetchall()]
        cursor = await self.conn.execute("SELECT * FROM observations WHERE status = 'active'")
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


class SearchRepository(BaseSQLiteRepository, ISearchRepository):
    async def perform_fts_search(
        self,
        fts_table: str,
        id_col: str,
        content_col: str,
        title_col: str,
        fts_query: str,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            f"SELECT {id_col}, {content_col}, {title_col}, bm25({fts_table}) "
            f"FROM {fts_table} WHERE {fts_table} MATCH ?",
            (fts_query,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def perform_like_search(
        self, table: str, id_col: str, content_col: str, query: str
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            f"SELECT {id_col}, {content_col} FROM {table} "
            f"WHERE ({content_col} LIKE ? OR {id_col} LIKE ?)",
            (f"%{query}%", f"%{query}%"),
        )
        return [dict(r) for r in await cursor.fetchall()]


class MetadataRepository(BaseSQLiteRepository, IMetadataRepository):
    async def get_all_metadata(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_access(self, content_id: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO knowledge_metadata (
                content_id, access_count, last_accessed,
                importance_score, stability, decay_rate
            )
            VALUES (?, 1, CURRENT_TIMESTAMP, 1.0, 1.1, 0.01)
            ON CONFLICT(content_id) DO UPDATE SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP,
                stability = stability * 1.1
            """,
            (content_id,),
        )

    async def get_access_stats_summary(self) -> dict[str, Any]:
        cursor = await self.conn.execute(
            "SELECT SUM(access_count), COUNT(*) FROM knowledge_metadata"
        )
        row = await cursor.fetchone()
        return {"total_access": row[0] or 0, "accessed_units": row[1] or 0}

    async def get_successful_search_stats(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT results_count, hit_content_ids, avg_similarity, timestamp "
            "FROM search_stats WHERE results_count > 0"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_total_search_count(self) -> int:
        cursor = await self.conn.execute("SELECT COUNT(*) FROM search_stats")
        row = await cursor.fetchone()
        return row[0] or 0

    async def log_search_stat(
        self, query: str, results_count: int, hit_ids: list[str], avg_sim: float = 0.0
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO search_stats (
                query, results_count, hit_content_ids, avg_similarity
            ) VALUES (?, ?, ?, ?)
            """,
            (query, results_count, json.dumps(hit_ids), avg_sim),
        )


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
            "USING fts5(session_id, thought, content='thought_history')"
        )
        # Triggers for FTS
        await self.conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS thought_history_ai AFTER INSERT ON thought_history BEGIN
                INSERT INTO thought_history_fts(rowid, session_id, thought) 
                VALUES (new.rowid, new.session_id, new.thought);
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


class ManagementRepository(BaseSQLiteRepository, IManagementRepository):
    async def get_table_info(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in await cursor.fetchall()]
        results = []
        for table in tables:
            try:
                c = await self.conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = (await c.fetchone())[0]
                results.append({"name": table, "count": count})
            except Exception as e:
                logger.warning(f"Failed to get count for table {table}: {e}")
                continue
        return results

    async def vacuum_into(self, target_path: str) -> None:
        await self.conn.execute(f"VACUUM INTO '{target_path}'")

    async def delete_stale_knowledge(self, age_days: int) -> int:
        # Mark as inactive instead of deleting for safety
        await self.conn.execute(
            """
            UPDATE entities SET status = 'inactive'
            WHERE importance < 3 
            AND created_at < date('now', ?)
            """,
            (f"-{age_days} days",),
        )
        return self.conn.total_changes

    async def get_count(self, table_name: str) -> int:
        try:
            cursor = await self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            row = await cursor.fetchone()
            return row[0] or 0
        except Exception as e:
            logger.warning(f"Failed to get count for table {table_name}: {e}")
            return 0

    async def get_creation_timestamp(self, content_id: str) -> str | None:
        query = (
            "SELECT created_at FROM entities WHERE name = ? "
            "UNION "
            "SELECT last_synced as created_at FROM bank_files WHERE filename = ?"
        )
        cursor = await self.conn.execute(query, (content_id, content_id))
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_database_stats(self) -> dict[str, Any]:
        stats = {}
        cursor = await self.conn.execute("PRAGMA page_count")
        stats["page_count"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA page_size")
        stats["page_size"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA freelist_count")
        stats["freelist_count"] = (await cursor.fetchone())[0]
        cursor = await self.conn.execute("PRAGMA journal_mode")
        stats["journal_mode"] = (await cursor.fetchone())[0]

        stats["fragmentation_ratio"] = (
            stats["freelist_count"] / stats["page_count"] if stats["page_count"] > 0 else 0
        )
        stats["wal_mode"] = stats["journal_mode"].lower() == "wal"
        return stats

    async def get_embedding_model_distribution(self) -> dict[str, int]:
        cursor = await self.conn.execute(
            "SELECT model_name, COUNT(*) FROM embeddings GROUP BY model_name"
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def get_isolated_entities(self) -> list[str]:
        # Entities not present in relations as subject or object
        query = """
            SELECT name FROM entities 
            WHERE status = 'active'
            AND name NOT IN (SELECT DISTINCT subject FROM relations WHERE status = 'active')
            AND name NOT IN (SELECT DISTINCT object FROM relations WHERE status = 'active')
        """
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_entity_type_distribution(self) -> dict[str, int]:
        cursor = await self.conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities "
            "WHERE status = 'active' GROUP BY entity_type"
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def get_agent_contribution_stats(self) -> dict[str, int]:
        # Aggregating from entities and observations
        query = """
            SELECT created_by, COUNT(*) FROM (
                SELECT created_by FROM entities
                UNION ALL
                SELECT created_by FROM observations
            ) GROUP BY created_by
        """
        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()
        return {r[0] or "unknown": r[1] for r in rows}

    async def get_snapshot_path(self, snapshot_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def insert_snapshot(self, name: str, description: str, file_path: str) -> None:
        await self.conn.execute(
            "INSERT INTO snapshots (name, description, file_path) VALUES (?, ?, ?)",
            (name, description, file_path),
        )

    async def list_snapshots(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT id, name, timestamp FROM snapshots ORDER BY timestamp DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def optimize_database(self) -> None:
        await self.conn.execute("PRAGMA optimize")
        await self.conn.execute("ANALYZE")

    async def get_low_activity_ids(self, before_date: str, max_access_count: int) -> list[str]:
        # Consider knowledge low-activity if it hasn't been accessed before before_date
        # and has access_count <= max_access_count.
        query = """
            SELECT content_id FROM knowledge_metadata
            WHERE last_accessed < ?
            AND access_count <= ?
        """
        cursor = await self.conn.execute(query, (before_date, max_access_count))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
