import random
import sqlite3
import time

from shared_memory.exceptions import DatabaseError, DatabaseLockedError
from shared_memory.utils import get_db_path, log_error


def retry_on_db_lock(max_retries=15, initial_delay=0.1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower():
                        retries += 1
                        if retries == max_retries:
                            raise DatabaseLockedError(
                                f"Database remained locked after {max_retries} attempts."
                            )
                        delay = min(
                            initial_delay * (2 ** (retries - 1)), 1.0
                        ) + random.uniform(0, 0.1)
                        time.sleep(delay)
                    else:
                        raise
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_connection():
    # Increase timeout to 30 seconds to handle heavy parallel writes (e.g. 100 agents)
    conn = sqlite3.connect(get_db_path(), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _add_column_if_missing(cursor, table, col_def):
    """
    Safely adds a column to a table if it doesn't already exist.
    """
    col_name = col_def.split()[0]
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]

    if col_name in columns:
        return

    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    except sqlite3.OperationalError as e:
        log_error(
            f"CRITICAL: Migration failed for table '{table}' adding '{col_def}'", e
        )
        raise


@retry_on_db_lock()
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            source TEXT,
            target TEXT,
            relation_type TEXT,
            justification TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            PRIMARY KEY (source, target, relation_type),
            FOREIGN KEY (source) REFERENCES entities (name) ON DELETE CASCADE,
            FOREIGN KEY (target) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (entity_name) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    # Embedding Cache (Phase 11 Optimization)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            content_hash TEXT PRIMARY KEY,
            vector BLOB,
            model_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_files (
            filename TEXT PRIMARY KEY,
            content TEXT,
            last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            content_id TEXT PRIMARY KEY,
            vector BLOB,
            model_name TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_metadata (
            content_id TEXT PRIMARY KEY,
            access_count INTEGER DEFAULT 0,
            last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
            stability REAL DEFAULT 0.1,
            importance_score REAL DEFAULT 0.1
        )
    """)
    cursor.execute("""
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL
        )
    """)
    # Conflicts table (New in Phase 13)
    cursor.execute("""
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
    # Troubleshooting Knowledge table (Decoupled Feature)
    cursor.execute("""
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
    _add_column_if_missing(cursor, "entities", "created_at DATETIME")
    _add_column_if_missing(cursor, "entities", "updated_at DATETIME")
    _add_column_if_missing(cursor, "entities", "created_by TEXT")
    _add_column_if_missing(cursor, "entities", "updated_by TEXT")
    _add_column_if_missing(cursor, "entities", "importance INTEGER DEFAULT 5")

    # Backfill if necessary (optional since we already have CURRENT_TIMESTAMP for new rows)
    # cursor.execute("UPDATE entities SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    _add_column_if_missing(cursor, "relations", "created_at DATETIME")
    _add_column_if_missing(cursor, "relations", "created_by TEXT")

    _add_column_if_missing(cursor, "observations", "created_by TEXT")

    _add_column_if_missing(cursor, "bank_files", "updated_by TEXT")
    _add_column_if_missing(cursor, "snapshots", "description TEXT")
    _add_column_if_missing(cursor, "snapshots", "file_path TEXT")
    _add_column_if_missing(cursor, "knowledge_metadata", "decay_rate REAL DEFAULT 0.01")

    conn.commit()
    conn.close()


@retry_on_db_lock()
async def update_access(content_id: str, conn=None):
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        conn.execute(
            """
            INSERT INTO knowledge_metadata (content_id, access_count, last_accessed, importance_score, stability, decay_rate)
            VALUES (?, 1, CURRENT_TIMESTAMP, 1.0, 1.1, 0.01)
            ON CONFLICT(content_id) DO UPDATE SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP,
                stability = stability * 1.1
        """,
            (content_id,),
        )
        conn.commit()
    except Exception as e:
        log_error(f"Failed to update access for {content_id}", e)
        raise DatabaseError(f"Failed to update access: {e}") from e
    finally:
        if should_close:
            conn.close()
