import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from ripen.cli.salvage import salvage_related_knowledge
from ripen.common.exceptions import DatabaseError
from ripen.common.utils import (
    get_logger,
    get_thoughts_db_path,
    log_error,
    log_info,
    mask_sensitive_data,
)
from ripen.infra.database import (
    _add_column_if_missing,
    async_get_thoughts_connection,
    retry_on_db_lock,
)

logger = get_logger("thought_logic")

# Throttling for background recovery
LAST_RECOVERY_TIME = datetime.min
RECOVERY_COOLDOWN = timedelta(minutes=10)
_THOUGHTS_INITIALIZED = False

# Session-level locks to serialize thought processing per session.
# NOTE: In extremely long-running servers with millions of unique sessions, 
# a periodic pruning of unused locks may be required to reclaim memory.
_SESSION_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@retry_on_db_lock()
async def init_thoughts_db(force: bool = False):
    """Initializes the separate thoughts database with optimized indices."""
    global _THOUGHTS_INITIALIZED
    if _THOUGHTS_INITIALIZED and not force:
        return
    db_path = get_thoughts_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    from ripen.infra.database import _async_get_connection_raw

    log_info(f"Initializing thoughts database at {db_path}...")
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
                agent_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration for existing databases
        cursor = await conn.cursor()
        await _add_column_if_missing(cursor, "thought_history", "distilled BOOLEAN DEFAULT 0")
        await _add_column_if_missing(cursor, "thought_history", "meta_data TEXT")
        await _add_column_if_missing(cursor, "thought_history", "agent_id TEXT")

        # Indices for performance and efficient sequence lookups
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thought_session ON thought_history (session_id)"
        )
        # Unique constraint to prevent duplicate thought numbers within a session
        try:
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_thought_number_unique "
                "ON thought_history (session_id, thought_number)"
            )
        except aiosqlite.IntegrityError:
            logger.error(
                "CRITICAL INTEGRITY WARNING: Duplicate thought_numbers detected in database. "
                "Unique constraint could not be applied at the DB level. "
                "Falling back to non-unique index. Please clean up duplicate data."
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thought_number "
                "ON thought_history (session_id, thought_number)"
            )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thought_timestamp ON thought_history (timestamp)"
        )
        # --- Full Text Search (FTS5) Support for Thoughts ---
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS thought_history_fts USING fts5(
                session_id, thought_number, thought, 
                content='thought_history', content_rowid='id'
            )
        """)

        # FTS Triggers for thought_history
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS thought_history_ai AFTER INSERT ON thought_history BEGIN
                INSERT INTO thought_history_fts(rowid, session_id, thought_number, thought) 
                VALUES (new.id, new.session_id, new.thought_number, new.thought);
            END;
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS thought_history_ad AFTER DELETE ON thought_history BEGIN
                INSERT INTO thought_history_fts(thought_history_fts, rowid, 
                                                 session_id, thought_number, thought) 
                VALUES('delete', old.id, old.session_id, old.thought_number, old.thought);
            END;
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS thought_history_au AFTER UPDATE ON thought_history BEGIN
                INSERT INTO thought_history_fts(thought_history_fts, rowid, 
                                                 session_id, thought_number, thought) 
                VALUES('delete', old.id, old.session_id, old.thought_number, old.thought);
                INSERT INTO thought_history_fts(rowid, session_id, thought_number, thought) 
                VALUES (new.id, new.session_id, new.thought_number, new.thought);
            END;
        """)

        # Population: Ensure existing thoughts are indexed
        await conn.execute("INSERT INTO thought_history_fts(thought_history_fts) VALUES('rebuild')")

        await conn.commit()
        _THOUGHTS_INITIALIZED = True
        log_info("Thoughts database initialization successful (FTS5 enabled).")


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
    session_id: str | None = None,
    agent_id: str = "default_agent",
) -> dict[str, Any]:
    """
    Implements the core logic for sequential thinking with security,
    validation, and persistence.
    """
    session_id = session_id or "default_session"

    async with _SESSION_LOCKS[session_id]:
        try:
            start_total = time.perf_counter()

            # 0. Infrastructure readiness
            # This ensures the DB exists even if the server
            # lifespan didn't run.
            from ripen.infra.database import init_db

            t_init_start = time.perf_counter()
            await init_db()
            await init_thoughts_db()
            dur_init = time.perf_counter() - t_init_start

            logger.info(
                f"Processing thought #{thought_number}/{total_thoughts} for session: {session_id}"
            )

            # 1. Security: Mask sensitive data
            masked_thought = mask_sensitive_data(thought)

            async with await async_get_thoughts_connection() as conn:
                # 2. Validation: Check sequence integrity
                # 2.1 Check for revisions
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
                
                # 2.2 Explicit Duplicate Check (UX/Performance)
                if not is_revision:
                    cursor = await conn.execute(
                        "SELECT id FROM thought_history "
                        "WHERE session_id = ? AND thought_number = ?",
                        (session_id, thought_number),
                    )
                    if await cursor.fetchone():
                        error_msg = (
                            f"Duplicate thought number: #{thought_number} "
                            f"already exists in session '{session_id}'. "
                            "If you intended to revise, set is_revision=True."
                        )
                        logger.warning(error_msg)
                        return {
                            "error": error_msg,
                            "thoughtNumber": thought_number,
                            "totalThoughts": total_thoughts,
                        }

                # 3. Persistence: Insert thought with metadata (filled post-search)
                t_db_start = time.perf_counter()
                try:
                    await conn.execute(
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
                            masked_thought,
                            1 if next_thought_needed else 0,
                            1 if is_revision else 0,
                            revises_thought,
                            branch_from_thought,
                            branch_id,
                            agent_id,
                            json.dumps({
                                "env": "development",
                                "timestamp": datetime.now().isoformat(),
                            }),
                        ),
                    )
                    await conn.commit()
                except aiosqlite.IntegrityError as ie:
                    await conn.rollback()
                    error_msg = f"Persistence failure (Duplicate ID): {ie}"
                    logger.error(
                        f"{error_msg} for session {session_id}, "
                        f"thought {thought_number}"
                    )
                    return {
                        "error": (
                            "Thought number already exists. "
                            "Please use a unique number or specify a revision."
                        ),
                        "details": str(ie),
                        "thoughtNumber": thought_number,
                        "totalThoughts": total_thoughts,
                    }
                
                dur_db = time.perf_counter() - t_db_start

                # 4. Statistics
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM thought_history WHERE session_id = ?",
                    (session_id,),
                )
                row = await cursor.fetchone()
                history_length = row[0] if row else 0

                branches = [r[0] for r in await cursor.fetchall()]

                await conn.commit()

            # 6. Salvage & Accretion (The Synergy)
            # 6.1 Accretion: Asynchronously extract and save new knowledge from this thought
            from ripen.core.distiller import incremental_distill_knowledge

            logger.info(f"Triggering incremental distillation for thought in session: {session_id}")
            from ripen.common.tasks import create_background_task

            create_background_task(
                incremental_distill_knowledge(session_id, thought),
                name=f"incremental_distill_{session_id}",
            )

            # 6.2 Salvage: Synchronously retrieve and rerank related past knowledge
            t_salvage_start = time.perf_counter()
            history = await get_thought_history(session_id)
            related_knowledge = await salvage_related_knowledge(thought, session_id, history)
            dur_salvage = time.perf_counter() - t_salvage_start

            # 6.3 Traceability: Record search results in metadata
            async with await async_get_thoughts_connection() as conn:
                search_meta = {
                    "hits_count": len(related_knowledge),
                    "hit_ids": [k["id"] for k in related_knowledge],
                    "env": "development",
                    "timestamp": datetime.now().isoformat(),
                }
                await conn.execute(
                    "UPDATE thought_history SET meta_data = ? "
                    "WHERE session_id = ? AND thought_number = ?",
                    (json.dumps(search_meta), session_id, thought_number),
                )
                await conn.commit()

            # 7. Opportunistic Recovery: Disabled during tests to prevent GHA hangs
            if "PYTEST_CURRENT_TEST" not in os.environ:
                from ripen.common.tasks import create_background_task

                create_background_task(
                    trigger_opportunistic_recovery(), name="opportunistic_recovery"
                )

            # 8. Final Distillation (Session Wrap-up)
            if not next_thought_needed:
                from ripen.core.distiller import auto_distill_knowledge

                # Ensure the complete history is analyzed one last time for synthesis
                await auto_distill_knowledge(session_id, history)
                async with await async_get_thoughts_connection() as conn:
                    await conn.execute(
                        "UPDATE thought_history SET distilled = 1 WHERE session_id = ?",
                        (session_id,),
                    )
                    await conn.commit()

            total_dur = time.perf_counter() - start_total
            logger.info(
                f"PERF [process_thought_core]: session={session_id} "
                f"total={total_dur:.3f}s (init={dur_init:.3f}s, db_insert={dur_db:.3f}s, "
                f"salvage={dur_salvage:.3f}s)"
            )

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


async def get_thought_history(session_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieves the thought history for a specific session."""
    session_id = session_id or "default_session"
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
        logger.info("Triggering opportunistic recovery of undistilled sessions...")
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
            from ripen.core.distiller import auto_distill_knowledge

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
