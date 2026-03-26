import sqlite3
from typing import Any

from shared_memory.database import retry_on_db_lock
from shared_memory.exceptions import DatabaseError
from shared_memory.utils import get_thoughts_db_path, log_error, mask_sensitive_data


@retry_on_db_lock()
def init_thoughts_db():
    """Initializes the separate thoughts database with optimized indices."""
    conn = sqlite3.connect(get_thoughts_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS thought_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            thought_number INTEGER NOT NULL,
            total_thoughts INTEGER NOT NULL,
            thought TEXT NOT NULL,
            next_thought_needed BOOLEAN,
            is_revision BOOLEAN DEFAULT 0,
            revises_thought INTEGER,
            branch_from_thought INTEGER,
            branch_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Indices for performance and efficient sequence lookups
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_thought_session ON thought_history (session_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_thought_number ON thought_history (session_id, thought_number)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_thought_timestamp ON thought_history (timestamp)"
    )
    conn.commit()
    conn.close()


def get_connection():
    conn = sqlite3.connect(get_thoughts_db_path())
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@retry_on_db_lock()
async def process_thought_core(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: bool = False,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    session_id: str = "default_session",
) -> dict[str, Any]:
    """
    Implements the core logic for sequential thinking with security, validation, and persistence.
    """
    try:
        # 1. Security: Mask sensitive data in the thought content
        masked_thought = mask_sensitive_data(thought)

        conn = get_connection()
        cursor = conn.cursor()

        # 2. Validation: Check sequence integrity
        if is_revision and revises_thought:
            cursor.execute(
                "SELECT id FROM thought_history WHERE session_id = ? AND thought_number = ?",
                (session_id, revises_thought),
            )
            if not cursor.fetchone():
                return {
                    "error": f"Invalid revision: Thought #{revises_thought} does not exist in session '{session_id}'",
                    "thoughtNumber": thought_number,
                    "totalThoughts": total_thoughts,
                }

        # 3. Persistence: Insert thought into the database
        cursor.execute(
            """
            INSERT INTO thought_history (
                session_id, thought_number, total_thoughts, thought, 
                next_thought_needed, is_revision, revises_thought, 
                branch_from_thought, branch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                thought_number,
                total_thoughts,
                masked_thought,
                1 if next_thought_needed else 0,
                1 if is_revision else 0,
                revises_thought,
                branch_from_thought,
                branch_id,
            ),
        )
        conn.commit()

        # 4. Statistics: Get current state for return object
        cursor.execute(
            "SELECT COUNT(*) FROM thought_history WHERE session_id = ?",
            (session_id,),
        )
        history_length = cursor.fetchone()[0]

        cursor.execute(
            "SELECT DISTINCT branch_id FROM thought_history WHERE session_id = ? AND branch_id IS NOT NULL",
            (session_id,),
        )
        branches = [r[0] for r in cursor.fetchall()]

        conn.close()

        # 5. Distillation: If session is complete, trigger knowledge extraction
        if not next_thought_needed:
            # We import here to avoid circular dependencies
            from shared_memory.distiller import auto_distill_knowledge
            history = await get_thought_history(session_id)
            # Sync wait for validation phase
            await auto_distill_knowledge(session_id, history)

        return {
            "thoughtNumber": thought_number,
            "totalThoughts": total_thoughts,
            "nextThoughtNeeded": next_thought_needed,
            "branches": branches,
            "thoughtHistoryLength": history_length,
        }

    except Exception as e:
        log_error(f"Critical failure in sequential thinking session {session_id}", e)
        raise DatabaseError(f"Reasoning persistence failed: {e}") from e


async def get_thought_history(
    session_id: str = "default_session",
) -> list[dict[str, Any]]:
    """Retrieves the thought history for a specific session."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM thought_history WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        log_error(f"Failed to retrieve history for session {session_id}", e)
        return []
