import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from shared_memory.database import (
    _add_column_if_missing,
    async_get_thoughts_connection,
    retry_on_db_lock,
)
from shared_memory.exceptions import DatabaseError
from shared_memory.search import perform_keyword_search
from shared_memory.utils import (
    get_thoughts_db_path,
    log_error,
    log_info,
    mask_sensitive_data,
)

# Throttling for background recovery
LAST_RECOVERY_TIME = datetime.min
RECOVERY_COOLDOWN = timedelta(minutes=10)
_THOUGHTS_INITIALIZED = False


@retry_on_db_lock()
async def init_thoughts_db(force: bool = False):
    """Initializes the separate thoughts database with optimized indices."""
    global _THOUGHTS_INITIALIZED
    if _THOUGHTS_INITIALIZED and not force:
        return
    db_path = get_thoughts_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    from shared_memory.database import _async_get_connection_raw

    async with await _async_get_connection_raw(db_path, is_thoughts=True) as conn:
        # Tables for thoughts
        await conn.execute("""
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
                distilled BOOLEAN DEFAULT 0,
                meta_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration for existing databases
        cursor = await conn.cursor()
        await _add_column_if_missing(
            cursor, "thought_history", "distilled BOOLEAN DEFAULT 0"
        )
        await _add_column_if_missing(
            cursor, "thought_history", "meta_data TEXT"
        )

        # Indices for performance and efficient sequence lookups
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thought_session "
            "ON thought_history (session_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thought_number "
            "ON thought_history (session_id, thought_number)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thought_timestamp "
            "ON thought_history (timestamp)"
        )
        await conn.commit()
        _THOUGHTS_INITIALIZED = True


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
    Implements the core logic for sequential thinking with security,
    validation, and persistence.
    """
    try:
        # Lazy initialization for both databases to handle cases where
        # lifespan didn't run.
        from shared_memory.database import init_db

        await init_db()
        await init_thoughts_db()

        # 1. Security: Mask sensitive data
        masked_thought = mask_sensitive_data(thought)

        async with await async_get_thoughts_connection() as conn:
            # 2. Validation: Check sequence integrity
            if is_revision and revises_thought:
                cursor = await conn.execute(
                    "SELECT id FROM thought_history "
                    "WHERE session_id = ? AND thought_number = ?",
                    (session_id, revises_thought),
                )
                if not await cursor.fetchone():
                    error_msg = (
                        f"Invalid revision: Thought #{revises_thought} "
                        f"does not exist in session '{session_id}'"
                    )
                    return {
                        "error": error_msg,
                        "thoughtNumber": thought_number,
                        "totalThoughts": total_thoughts,
                    }

            # 3. Persistence: Insert thought with metadata (filled post-search)
            await conn.execute(
                """
                INSERT INTO thought_history (
                    session_id, thought_number, total_thoughts, thought,
                    next_thought_needed, is_revision, revises_thought,
                    branch_from_thought, branch_id, meta_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(
                        {"env": "development", "timestamp": datetime.now().isoformat()}
                    ),
                ),
            )
            await conn.commit()

            # 4. Statistics
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM thought_history WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            history_length = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT DISTINCT branch_id FROM thought_history "
                "WHERE session_id = ? AND branch_id IS NOT NULL",
                (session_id,),
            )
            branches = [r[0] for r in await cursor.fetchall()]

            # 5. Distillation
            if not next_thought_needed:
                from shared_memory.distiller import auto_distill_knowledge

                history = await get_thought_history(session_id)
                await auto_distill_knowledge(session_id, history)
                await conn.execute(
                    "UPDATE thought_history SET distilled = 1 WHERE session_id = ?",
                    (session_id,),
                )
                await conn.commit()

        # 6. Knowledge Injection
        related_knowledge = await perform_keyword_search(
            thought, limit=3, exclude_session_id=session_id
        )

        # 6.1 Traceability: Record search results in metadata
        async with await async_get_thoughts_connection() as conn:
            search_meta = {
                "hits_count": len(related_knowledge),
                "hit_ids": [k["id"] for k in related_knowledge],
                "env": "development",
                "timestamp": datetime.now().isoformat()
            }
            await conn.execute(
                "UPDATE thought_history SET meta_data = ? "
                "WHERE session_id = ? AND thought_number = ?",
                (json.dumps(search_meta), session_id, thought_number)
            )
            await conn.commit()

        # 7. Opportunistic Recovery: Disabled during tests to prevent GHA hangs
        if "PYTEST_CURRENT_TEST" not in os.environ:
            asyncio.create_task(trigger_opportunistic_recovery())

        return {
            "thoughtNumber": thought_number,
            "totalThoughts": total_thoughts,
            "nextThoughtNeeded": next_thought_needed,
            "branches": branches,
            "thoughtHistoryLength": history_length,
            "related_knowledge": related_knowledge,
        }

    except Exception as e:
        log_error(f"Critical failure in sequential thinking session {session_id}", e)
        raise DatabaseError(f"Reasoning persistence failed: {e}") from e


async def get_thought_history(
    session_id: str = "default_session",
) -> list[dict[str, Any]]:
    """Retrieves the thought history for a specific session."""
    try:
        async with await async_get_thoughts_connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM thought_history WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log_error(f"Failed to retrieve history for session {session_id}", e)
        return []


async def trigger_opportunistic_recovery():
    """Triggers recovery if the cooldown has passed."""
    global LAST_RECOVERY_TIME
    now = datetime.now()
    if now - LAST_RECOVERY_TIME > RECOVERY_COOLDOWN:
        LAST_RECOVERY_TIME = now
        await recover_undistilled_sessions()


async def recover_undistilled_sessions():
    """
    Finds and processes sessions that were never distilled.
    """
    try:
        async with await async_get_thoughts_connection() as conn:
            cursor = await conn.execute("""
                SELECT DISTINCT session_id FROM thought_history
                WHERE distilled = 0 AND next_thought_needed = 0
            """)
            sessions_to_recover = [row[0] for row in await cursor.fetchall()]

            cursor = await conn.execute("""
                SELECT DISTINCT session_id FROM thought_history
                WHERE distilled = 0
                GROUP BY session_id
                HAVING MAX(timestamp) < datetime('now', '-30 minutes')
            """)
            stale_sessions = [row[0] for row in await cursor.fetchall()]

            all_to_process = list(set(sessions_to_recover + stale_sessions))

            if not all_to_process:
                return

            log_info(f"Found {len(all_to_process)} undistilled sessions to recover.")
            from shared_memory.distiller import auto_distill_knowledge

            for sess_id in all_to_process:
                history = await get_thought_history(sess_id)
                if history:
                    await auto_distill_knowledge(sess_id, history)
                    await conn.execute(
                        "UPDATE thought_history SET distilled = 1 WHERE session_id = ?",
                        (sess_id,),
                    )
                    await conn.commit()
    except Exception as e:
        log_error("Failed during opportunistic thought recovery", e)
