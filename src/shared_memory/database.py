import asyncio
import random

import aiosqlite

from shared_memory.exceptions import DatabaseError, DatabaseLockedError
from shared_memory.utils import get_db_path, log_error


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

    def __init__(self, db_path: str, timeout: float = 30.0, is_thoughts: bool = False):
        self.db_path = db_path
        self.timeout = timeout
        self.is_thoughts = is_thoughts
        self.conn = None

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
            return self.conn
        except (aiosqlite.Error, sqlite3.Error) as e:
            log_error(f"Failed to connect to database at {self.db_path}", e)
            raise DatabaseError(f"Database connection failed: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.conn.close()

    def __await__(self):
        # This allows 'await async_get_connection()' to return 'self'
        async def _internal():
            return self

        return _internal().__await__()


async def async_get_connection():
    """
    Returns an AsyncSQLiteConnection wrapper for the main database.
    Usage: async with await async_get_connection() as conn:
    """
    return AsyncSQLiteConnection(get_db_path())


async def async_get_thoughts_connection():
    """
    Returns an AsyncSQLiteConnection wrapper for the thoughts database.
    Usage: async with await async_get_thoughts_connection() as conn:
    """
    from shared_memory.utils import get_thoughts_db_path

    return AsyncSQLiteConnection(get_thoughts_db_path(), is_thoughts=True)


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
async def init_db():
    async with await async_get_connection() as conn:
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
        # Search Stats table for Hit Rate calculation
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query TEXT,
                results_count INTEGER
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

        await conn.commit()


@retry_on_db_lock()
async def update_access(content_id: str, conn=None):
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
async def log_search_stat(query: str, results_count: int):
    """Logs the result count of a search for hit rate calculation."""
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO search_stats (query, results_count) VALUES (?, ?)",
            (query, results_count),
        )
        await conn.commit()
