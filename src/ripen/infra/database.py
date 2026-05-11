import asyncio
import os
import random
import sqlite3

import aiosqlite

from ripen.common.exceptions import DatabaseError, DatabaseLockedError
from ripen.common.utils import get_db_path, get_logger, log_error

logger = get_logger("database")

# Global singletons for persistent connections
_MAIN_CONNECTION: aiosqlite.Connection | None = None
_THOUGHTS_CONNECTION: aiosqlite.Connection | None = None

# Global lock to prevent race conditions during singleton initialization
_INIT_LOCK: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    global _INIT_LOCK
    if _INIT_LOCK is None:
        _INIT_LOCK = asyncio.Lock()
    return _INIT_LOCK


# Global semaphores mapped by event loop to limit concurrent DB writes
_WRITE_SEMAPHORES: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def get_write_semaphore() -> asyncio.Semaphore:
    """Returns a write semaphore bound to the current event loop."""
    loop = asyncio.get_running_loop()
    if loop not in _WRITE_SEMAPHORES:
        _WRITE_SEMAPHORES[loop] = asyncio.Semaphore(1)
    return _WRITE_SEMAPHORES[loop]


# Global flag to track if the main database has been initialized in the current session.
_DB_INITIALIZED = False


def retry_on_db_lock(max_retries=15, initial_delay=0.1):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except (aiosqlite.OperationalError, DatabaseError, sqlite3.OperationalError) as e:
                    error_str = str(e).lower()
                    if "database is locked" in error_str:
                        retries += 1
                        delay = min(initial_delay * (2 ** (retries - 1)), 1.0) + random.uniform(
                            0, 0.1
                        )
                        logger.warning(
                            f"DATABASE LOCKED: Attempt {retries}/{max_retries}. "
                            f"Waiting {delay:.2f}s before retry. "
                            f"(Source: {func.__name__}, Error: {e})"
                        )
                        if retries == max_retries:
                            logger.error(
                                f"DATABASE FATAL: Max retries ({max_retries}) "
                                f"exceeded for {func.__name__}. Giving up."
                            )
                            raise DatabaseLockedError(
                                f"Database remained locked after {max_retries} attempts."
                            ) from e
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"DATABASE ERROR: Non-lock error in {func.__name__}: {e}")
                        raise e
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class AsyncSQLiteConnection:
    """
    A context manager that returns the Singleton connection for the database.
    Does NOT close the connection on exit (managed by server lifespan).
    """

    def __init__(self, db_path: str, is_thoughts: bool = False):
        self.db_path = db_path
        self.is_thoughts = is_thoughts
        self.conn = None

    async def __aenter__(self):
        global _MAIN_CONNECTION, _THOUGHTS_CONNECTION
        try:
            async with _get_init_lock():
                if self.is_thoughts:
                    if _THOUGHTS_CONNECTION is None:
                        logger.info(f"Establishing NEW thoughts singleton: {self.db_path}")
                        _THOUGHTS_CONNECTION = await aiosqlite.connect(self.db_path, timeout=30.0)
                        _THOUGHTS_CONNECTION.row_factory = aiosqlite.Row
                        # --- MATURE TECH OPTIMIZATIONS ---
                        await _THOUGHTS_CONNECTION.execute("PRAGMA journal_mode = WAL")
                        await _THOUGHTS_CONNECTION.execute("PRAGMA synchronous = NORMAL")
                        await _THOUGHTS_CONNECTION.execute("PRAGMA mmap_size = 268435456")  # 256MB
                        await _THOUGHTS_CONNECTION.execute("PRAGMA temp_store = MEMORY")
                        await _THOUGHTS_CONNECTION.execute("PRAGMA busy_timeout = 5000")
                        logger.info("Thoughts connection PRAGMAs configured (WAL/NORMAL/MMAP).")
                    self.conn = _THOUGHTS_CONNECTION
                else:
                    if _MAIN_CONNECTION is None:
                        logger.info(f"Establishing NEW singleton connection to: {self.db_path}")
                        try:
                            _MAIN_CONNECTION = await aiosqlite.connect(self.db_path, timeout=30.0)
                            _MAIN_CONNECTION.row_factory = aiosqlite.Row
                            # --- MATURE TECH OPTIMIZATIONS ---
                            await _MAIN_CONNECTION.execute("PRAGMA foreign_keys = ON")
                            await _MAIN_CONNECTION.execute("PRAGMA journal_mode = WAL")
                            await _MAIN_CONNECTION.execute("PRAGMA synchronous = NORMAL")
                            await _MAIN_CONNECTION.execute("PRAGMA mmap_size = 268435456")  # 256MB
                            await _MAIN_CONNECTION.execute("PRAGMA temp_store = MEMORY")
                            await _MAIN_CONNECTION.execute("PRAGMA busy_timeout = 5000")
                            await _MAIN_CONNECTION.execute("PRAGMA cache_size = -64000")  # ~64MB
                            logger.info("Main connection successfully established and configured.")
                        except Exception as e:
                            logger.error(f"CRITICAL: Failed to establish main DB connection: {e}")
                            raise
                    self.conn = _MAIN_CONNECTION

            logger.debug(
                f"AsyncSQLiteConnection: Returning connection for {self.db_path} "
                f"(is_thoughts={self.is_thoughts})"
            )
            return self.conn
        except Exception as e:
            from ripen.common.exceptions import DatabaseError

            logger.exception("Failed to connect to database at {db_path}", db_path=self.db_path)
            log_error(f"Failed to connect to database at {self.db_path}", e)
            raise DatabaseError(f"Database connection failed: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type and not isinstance(exc_val, asyncio.CancelledError):
            logger.error(
                f"Exception detected in AsyncSQLiteConnection context for {self.db_path}: "
                f"{exc_type.__name__}: {exc_val}"
            )
        # We don't close the connection here as it's a managed singleton
        return False

    def __await__(self):
        async def _internal():
            return self

        return _internal().__await__()


async def close_all_connections():
    """
    Closes all singleton connections. Should be called during server shutdown
    or between tests to ensure isolation.
    """
    global _MAIN_CONNECTION, _THOUGHTS_CONNECTION, _DB_INITIALIZED
    logger.info("Closing all singleton database connections...")
    async with _get_init_lock():
        if _MAIN_CONNECTION:
            await _MAIN_CONNECTION.close()
            _MAIN_CONNECTION = None
            logger.info("Main connection closed.")
        if _THOUGHTS_CONNECTION:
            await _THOUGHTS_CONNECTION.close()
            _THOUGHTS_CONNECTION = None
            logger.info("Thoughts connection closed.")
        _DB_INITIALIZED = False


async def async_get_connection():
    """
    [DEPRECATED] Legacy connection helper. Use UnitOfWork or AsyncSQLiteConnection directly.
    """
    await init_db()
    return await AsyncSQLiteConnection(get_db_path())


async def async_get_thoughts_connection():
    """
    [DEPRECATED] Legacy thoughts connection helper. 
    Use UnitOfWork or AsyncSQLiteConnection directly.
    """
    from ripen.common.utils import get_thoughts_db_path
    from ripen.core.thought_logic import init_thoughts_db

    await init_thoughts_db()
    return await AsyncSQLiteConnection(get_thoughts_db_path(), is_thoughts=True)


async def _async_get_connection_raw(db_path: str, is_thoughts: bool = False):
    """
    INTERNAL USE ONLY. Returns a connection wrapper without triggering
    lazy initialization.
    """
    return AsyncSQLiteConnection(db_path, is_thoughts=is_thoughts)


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
        log_error(f"CRITICAL: Migration failed for table '{table}' adding '{col_def}'", e)
        raise


@retry_on_db_lock()
async def init_db(force: bool = False):
    global _DB_INITIALIZED
    if force:
        _DB_INITIALIZED = False
        await close_all_connections()

    if _DB_INITIALIZED:
        return

    logger.info(f"Initializing main database (force={force})...")

    # Ensure directory exists
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with await _async_get_connection_raw(db_path) as conn:
        # Integrity Check: verify file is a database
        try:
            await conn.execute("SELECT 1")
            logger.info("DB Integrity Check: PASSED.")
        except (aiosqlite.DatabaseError, sqlite3.DatabaseError) as e:
            logger.error(f"DB Integrity Check: FAILED for {db_path}. {e}")
            raise

        logger.debug(f"Starting table creation/verification sequence for {db_path}...")
        cursor = await conn.cursor()
        try:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    name TEXT PRIMARY KEY,
                    entity_type TEXT,
                    description TEXT,
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    updated_by TEXT,
                    status TEXT DEFAULT 'active'
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
                    status TEXT DEFAULT 'active',
                    PRIMARY KEY (subject, object, predicate)
                )
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_name TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
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
                    updated_by TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            logger.info("Core tables (entities, relations, observations, bank_files) verified.")
        except Exception:
            logger.exception("CRITICAL: Failed to create/verify core tables")
            raise
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
                agent_id TEXT,
                meta_data TEXT
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
                avg_similarity REAL DEFAULT 0.0,
                meta_data TEXT
            )
        """)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL,
                content_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                UNIQUE(tag, content_id, content_type)
            )
        """)
        await cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
        await cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_content ON tags(content_id)")

        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS troubleshooting_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                solution TEXT NOT NULL,
                affected_functions TEXT,
                env_metadata TEXT,
                access_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await _add_column_if_missing(cursor, "entities", "created_at DATETIME")
        await _add_column_if_missing(cursor, "entities", "updated_at DATETIME")
        await _add_column_if_missing(cursor, "entities", "created_by TEXT")
        await _add_column_if_missing(cursor, "entities", "updated_by TEXT")
        await _add_column_if_missing(cursor, "entities", "importance INTEGER DEFAULT 5")
        await _add_column_if_missing(cursor, "audit_logs", "meta_data TEXT")
        await _add_column_if_missing(cursor, "search_stats", "meta_data TEXT")

        await _add_column_if_missing(cursor, "relations", "created_at DATETIME")
        await _add_column_if_missing(cursor, "relations", "created_by TEXT")

        await _add_column_if_missing(cursor, "observations", "created_by TEXT")

        await _add_column_if_missing(cursor, "bank_files", "updated_by TEXT")
        await _add_column_if_missing(cursor, "entities", "status TEXT DEFAULT 'active'")
        await _add_column_if_missing(cursor, "relations", "status TEXT DEFAULT 'active'")
        await _add_column_if_missing(cursor, "observations", "status TEXT DEFAULT 'active'")
        await _add_column_if_missing(cursor, "bank_files", "status TEXT DEFAULT 'active'")

        await _add_column_if_missing(cursor, "snapshots", "description TEXT")
        await _add_column_if_missing(cursor, "snapshots", "file_path TEXT")
        await _add_column_if_missing(cursor, "knowledge_metadata", "decay_rate REAL DEFAULT 0.01")
        await _add_column_if_missing(cursor, "search_stats", "hit_content_ids TEXT")
        await _add_column_if_missing(cursor, "search_stats", "avg_similarity REAL DEFAULT 0.0")

        # --- Full Text Search (FTS5) Support ---
        await cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                name, description, 
                content='entities'
            )
        """)
        await cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
                entity_name, content, 
                content='observations', content_rowid='id'
            )
        """)
        await cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS bank_files_fts USING fts5(
                filename, content, 
                content='bank_files'
            )
        """)
        await cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS troubleshooting_knowledge_fts USING fts5(
                title, solution, affected_functions,
                content='troubleshooting_knowledge', content_rowid='id'
            )
        """)

        # FTS Triggers: entities
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
                INSERT INTO entities_fts(rowid, name, description) 
                VALUES (new.rowid, new.name, new.description);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, description) 
                VALUES('delete', old.rowid, old.name, old.description);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, description) 
                VALUES('delete', old.rowid, old.name, old.description);
                INSERT INTO entities_fts(rowid, name, description) 
                VALUES (new.rowid, new.name, new.description);
            END;
        """)

        # FTS Triggers: observations
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
                INSERT INTO observations_fts(rowid, entity_name, content) 
                VALUES (new.id, new.entity_name, new.content);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, entity_name, content) 
                VALUES('delete', old.id, old.entity_name, old.content);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, entity_name, content) 
                VALUES('delete', old.id, old.entity_name, old.content);
                INSERT INTO observations_fts(rowid, entity_name, content) 
                VALUES (new.id, new.entity_name, new.content);
            END;
        """)

        # FTS Triggers: bank_files
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS bank_files_ai AFTER INSERT ON bank_files BEGIN
                INSERT INTO bank_files_fts(rowid, filename, content) 
                VALUES (new.rowid, new.filename, new.content);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS bank_files_ad AFTER DELETE ON bank_files BEGIN
                INSERT INTO bank_files_fts(bank_files_fts, rowid, filename, content) 
                VALUES('delete', old.rowid, old.filename, old.content);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS bank_files_au AFTER UPDATE ON bank_files BEGIN
                INSERT INTO bank_files_fts(bank_files_fts, rowid, filename, content) 
                VALUES('delete', old.rowid, old.filename, old.content);
                INSERT INTO bank_files_fts(rowid, filename, content) 
                VALUES (new.rowid, new.filename, new.content);
            END;
        """)

        # FTS Triggers: troubleshooting_knowledge
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS troubleshooting_ai
            AFTER INSERT ON troubleshooting_knowledge BEGIN
                INSERT INTO troubleshooting_knowledge_fts
                    (rowid, title, solution, affected_functions)
                VALUES (new.id, new.title, new.solution, new.affected_functions);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS troubleshooting_ad
            AFTER DELETE ON troubleshooting_knowledge BEGIN
                INSERT INTO troubleshooting_knowledge_fts(
                    troubleshooting_knowledge_fts, rowid, title, solution, affected_functions
                )
                VALUES('delete', old.id, old.title, old.solution, old.affected_functions);
            END;
        """)
        await cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS troubleshooting_au
            AFTER UPDATE ON troubleshooting_knowledge BEGIN
                INSERT INTO troubleshooting_knowledge_fts(
                    troubleshooting_knowledge_fts, rowid, title, solution, affected_functions
                )
                VALUES(
                    'delete', old.id, old.title, old.solution, old.affected_functions
                );
                INSERT INTO troubleshooting_knowledge_fts
                    (rowid, title, solution, affected_functions)
                VALUES (new.id, new.title, new.solution, new.affected_functions);
            END;
        """)

        # Population: Ensure existing data is indexed
        await cursor.execute("INSERT INTO entities_fts(entities_fts) VALUES('rebuild')")
        await cursor.execute("INSERT INTO observations_fts(observations_fts) VALUES('rebuild')")
        await cursor.execute("INSERT INTO bank_files_fts(bank_files_fts) VALUES('rebuild')")
        await cursor.execute(
            "INSERT INTO troubleshooting_knowledge_fts(troubleshooting_knowledge_fts) "
            "VALUES('rebuild')"
        )

        await conn.commit()

        # --- RUN MIGRATIONS ---
        from ripen.migrations.manager import MigrationManager

        migrator = MigrationManager(get_db_path())
        await migrator.run_migrations(conn)

        # Final Verification: Ensure critical tables exist before marking as initialized
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
        )
        if not await cursor.fetchone():
            _DB_INITIALIZED = False
            log_error("Critical failure: 'entities' table missing after init_db.")
        else:
            _DB_INITIALIZED = True
            logger.info("Main database initialization successful.")
