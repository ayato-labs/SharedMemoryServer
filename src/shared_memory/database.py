import asyncio
import os
import random

import aiosqlite

from shared_memory.exceptions import DatabaseError, DatabaseLockedError
from shared_memory.utils import get_db_path, log_error


# Global flag to track if the main database has been initialized in the current session.
_DB_INITIALIZED = False


def retry_on_db_lock(max_retries=15, initial_delay=0.1):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except (aiosqlite.OperationalError, DatabaseError) as e:
                    error_str = str(e).lower()
                    if "database is locked" in error_str:
                        retries += 1
                        if retries == max_retries:
                            raise DatabaseLockedError(
                                f"Database remained locked after {max_retries} "
                                "attempts."
                            ) from e
                        delay = min(
                            initial_delay * (2 ** (retries - 1)), 1.0
                        ) + random.uniform(0, 0.1)
                        await asyncio.sleep(delay)
                    else:
                        raise
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class AsyncSQLiteConnection:
    """
    A wrapper for aiosqlite.Connection that ensures exactly one 'start()' call
    even when used with the 'async with await' pattern.
    """

    _active_connections = set()

    def __init__(self, db_path: str, timeout: float = 30.0, is_thoughts: bool = False):
        self.db_path = db_path
        self.timeout = timeout
        self.is_thoughts = is_thoughts
        self.conn = None

    @classmethod
    def get_active_count(cls):
        return len(cls._active_connections)

    @classmethod
    async def close_all_active(cls):
        """Force close all tracked connections (Testing helper)."""
        import copy
        conns = copy.copy(cls._active_connections)
        for c in conns:
            try:
                await c.close()
            except Exception:
                pass
        cls._active_connections.clear()

    async def __aenter__(self):
        import sqlite3
        try:
            self.conn = await aiosqlite.connect(self.db_path, timeout=self.timeout)
            self.conn.row_factory = aiosqlite.Row

            # Apply global PRAGMAs
            if not self.is_thoughts:
                await self.conn.execute("PRAGMA foreign_keys = ON")
            await self.conn.execute("PRAGMA journal_mode = WAL")
            await self.conn.execute("PRAGMA synchronous = NORMAL")
            
            # Track connection for cleanup
            if "PYTEST_CURRENT_TEST" in os.environ:
                self._active_connections.add(self.conn)
                
            return self.conn
        except (aiosqlite.Error, sqlite3.Error) as e:
            log_error(f"Failed to connect to database at {self.db_path}", e)
            raise DatabaseError(f"Database connection failed: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if self.conn in self._active_connections:
                self._active_connections.discard(self.conn)
            await self.conn.close()
            self.conn = None

    def __await__(self):
        # This allows 'await async_get_connection()' to return 'self'
        async def _internal():
            return self

        return _internal().__await__()


async def _async_get_connection_raw(db_path: str, is_thoughts: bool = False):
    """
    INTERNAL USE ONLY. Returns a connection wrapper without triggering lazy initialization.
    Prevents infinite recursion during 'init_db'.
    """
    return AsyncSQLiteConnection(db_path, is_thoughts=is_thoughts)


async def async_get_connection():
    """
    Returns an AsyncSQLiteConnection wrapper for the main database.
    Guarantees that init_db() has been called before returning the connection.
    Usage: async with await async_get_connection() as conn:
    """
    await init_db()
    return await _async_get_connection_raw(get_db_path())


async def async_get_thoughts_connection():
    """
    Returns an AsyncSQLiteConnection wrapper for the thoughts database.
    Guarantees that init_thoughts_db() has been called.
    """
    from shared_memory.thought_logic import init_thoughts_db
    from shared_memory.utils import get_thoughts_db_path
    await init_thoughts_db()
    return await _async_get_connection_raw(get_thoughts_db_path(), is_thoughts=True)


async def _add_column_if_missing(cursor, table, col_def):
    """
    Safely adds a column to a table if it doesn't already exist.
    """
    col_name = col_def.split()[0]
    await cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in await cursor.fetchall()]

    if col_name in columns:
        return

    try:
        await cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    except aiosqlite.OperationalError as e:
        log_error(
            f"CRITICAL: Migration failed for table '{table}' adding '{col_def}'", e
        )
        raise


@retry_on_db_lock()
async def init_db(force: bool = False):
    global _DB_INITIALIZED
    if _DB_INITIALIZED and not force:
        return

    async with await _async_get_connection_raw(get_db_path()) as conn:
        cursor = await conn.cursor()
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                name TEXT PRIMARY KEY,
                entity_type TEXT,
                description TEXT,
                importance INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                subject TEXT,
                object TEXT,
                predicate TEXT,
                justification TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                PRIMARY KEY (subject, object, predicate),
                FOREIGN KEY (subject) REFERENCES entities (name) ON DELETE CASCADE,
                FOREIGN KEY (object) REFERENCES entities (name) ON DELETE CASCADE
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (entity_name) REFERENCES entities (name) ON DELETE CASCADE
            )
        """)
        # Explicit consistency check for critical tables
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                content_hash TEXT PRIMARY KEY,
                vector BLOB,
                model_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_files (
                filename TEXT PRIMARY KEY,
                content TEXT,
                last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                content_id TEXT PRIMARY KEY,
                vector BLOB,
                model_name TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_metadata (
                content_id TEXT PRIMARY KEY,
                access_count INTEGER DEFAULT 0,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                stability REAL DEFAULT 0.1,
                importance_score REAL DEFAULT 0.1
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                content_id TEXT,
                action TEXT,
                old_data TEXT,
                new_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                agent_id TEXT
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT NOT NULL
            )
        """)
        # Conflicts table (New in Phase 13)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT NOT NULL,
                existing_content TEXT NOT NULL,
                new_content TEXT NOT NULL,
                reason TEXT,
                agent_id TEXT,
                detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0
            )
        """)
        # Search Stats table for Hit Rate and Knowledge Age calculation
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query TEXT,
                results_count INTEGER,
                hit_content_ids TEXT,
                avg_similarity REAL DEFAULT 0.0
            )
        """)
        # Troubleshooting Knowledge table (Decoupled Feature)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS troubleshooting_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                solution TEXT NOT NULL,
                affected_functions TEXT,
                env_metadata TEXT,
                access_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await _add_column_if_missing(cursor, "entities", "created_at DATETIME")
        await _add_column_if_missing(cursor, "entities", "updated_at DATETIME")
        await _add_column_if_missing(cursor, "entities", "created_by TEXT")
        await _add_column_if_missing(cursor, "entities", "updated_by TEXT")
        await _add_column_if_missing(cursor, "entities", "importance INTEGER DEFAULT 5")

        await _add_column_if_missing(cursor, "relations", "created_at DATETIME")
        await _add_column_if_missing(cursor, "relations", "created_by TEXT")

        await _add_column_if_missing(cursor, "observations", "created_by TEXT")

        await _add_column_if_missing(cursor, "bank_files", "updated_by TEXT")
        await _add_column_if_missing(cursor, "snapshots", "description TEXT")
        await _add_column_if_missing(cursor, "snapshots", "file_path TEXT")
        await _add_column_if_missing(
            cursor, "knowledge_metadata", "decay_rate REAL DEFAULT 0.01"
        )
        await _add_column_if_missing(cursor, "search_stats", "hit_content_ids TEXT")
        await _add_column_if_missing(
            cursor, "search_stats", "avg_similarity REAL DEFAULT 0.0"
        )

        await conn.commit()
        _DB_INITIALIZED = True


@retry_on_db_lock()
async def update_access(content_id: str, conn=None):
    # Guard: Ensure DB is initialized before any access update
    await init_db()
    if conn is None:
        async with await async_get_connection() as conn:
            await conn.execute(
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
            await conn.commit()
    else:
        await conn.execute(
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

@retry_on_db_lock()
async def log_search_stat(
    query: str, results_count: int, hit_ids: list[str] = None, avg_sim: float = 0.0, conn=None
):
    """
    Logs the result count of a search for hit rate and knowledge age calculation.
    """
    # Guard: Ensure DB is initialized before logging stats
    await init_db()
    import json
    hit_ids_json = json.dumps(hit_ids or [])

    async def _execute(c):
        await c.execute(
            """
            INSERT INTO search_stats (
                query, results_count, hit_content_ids, avg_similarity
            ) VALUES (?, ?, ?, ?)
            """,
            (query, results_count, hit_ids_json, avg_sim),
        )
        await c.commit()

    if conn is not None:
        await _execute(conn)
    else:
        async with await async_get_connection() as conn:
            await _execute(conn)
