import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from ripen.common.utils import (
    get_logger,
    get_thoughts_db_path,
    mask_sensitive_data,
)
from ripen.infra.database import (
    AsyncSQLiteConnection,
    retry_on_db_lock,
)
from ripen.infra.uow import SecureWriteContext, UnitOfWork

logger = get_logger("thought_logic")

# Throttling for background recovery
LAST_RECOVERY_TIME = datetime.min
RECOVERY_COOLDOWN = timedelta(minutes=10)
_THOUGHTS_INITIALIZED = False

# Session-level locks to serialize thought processing per session.
_SESSION_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@retry_on_db_lock()
async def init_thoughts_db(force: bool = False):
    """Initializes the separate thoughts database with optimized indices."""
    global _THOUGHTS_INITIALIZED
    if _THOUGHTS_INITIALIZED and not force:
        return
    db_path = get_thoughts_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    from ripen.infra.database import _add_column_if_missing

    logger.info(f"Initializing thoughts database at {db_path}...")
    async with await AsyncSQLiteConnection(db_path, is_thoughts=True) as conn:
        from ripen.infra.repository import ThoughtRepository

        thoughts_repo = ThoughtRepository(conn)
        await thoughts_repo.init_tables()

        # Migration for existing databases
        cursor = await conn.cursor()
        await _add_column_if_missing(cursor, "thought_history", "distilled BOOLEAN DEFAULT 0")
        await _add_column_if_missing(cursor, "thought_history", "meta_data TEXT")
        await _add_column_if_missing(cursor, "thought_history", "agent_id TEXT")

        await conn.commit()
        _THOUGHTS_INITIALIZED = True
        logger.info("Thoughts database initialization successful (FTS5 enabled).")


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
            await init_thoughts_db()
            dur_init = time.perf_counter() - start_total

            logger.info(
                f"Processing thought #{thought_number}/{total_thoughts} for session: {session_id}"
            )

            # 1. Security: Mask sensitive data
            masked_thought = mask_sensitive_data(thought)

            async with SecureWriteContext(is_thoughts=True) as uow:
                # 2. Validation: Check sequence integrity
                history = await uow.thoughts.get_session_history(session_id)
                existing_numbers = [h["thought_number"] for h in history]

                if is_revision and revises_thought:
                    if revises_thought not in existing_numbers:
                        error_msg = (
                            f"Invalid revision: Thought #{revises_thought} "
                            f"does not exist in session '{session_id}'"
                        )
                        return {
                            "error": error_msg,
                            "thoughtNumber": thought_number,
                            "totalThoughts": total_thoughts,
                        }

                if not is_revision:
                    if thought_number in existing_numbers:
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

                # 3. Persistence: Insert thought
                t_db_start = time.perf_counter()
                meta_data = json.dumps(
                    {
                        "env": "development",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                await uow.thoughts.insert_thought(
                    session_id,
                    thought_number,
                    total_thoughts,
                    masked_thought,
                    next_thought_needed,
                    is_revision,
                    revises_thought,
                    branch_from_thought,
                    branch_id,
                    agent_id,
                    meta_data,
                )
                dur_db = time.perf_counter() - t_db_start

                # 4. Statistics
                history_length = len(history) + 1
                branches = []  # Placeholder

                # 6. Salvage & Accretion
                from ripen.common.tasks import create_background_task
                from ripen.core.distiller import incremental_distill_knowledge

                create_background_task(
                    incremental_distill_knowledge(session_id, thought),
                    name=f"incremental_distill_{session_id}",
                )

                # 6.2 Salvage (RAG component - uses main DB)
                t_salvage_start = time.perf_counter()
                from ripen.cli.salvage import salvage_related_knowledge

                try:
                    # Give salvage 15 seconds max, it's not critical if it fails
                    related_knowledge = await asyncio.wait_for(
                        salvage_related_knowledge(thought, session_id, history),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Salvage timed out for session {session_id}. Proceeding without it.")
                    related_knowledge = []
                except Exception as e:
                    logger.error(f"Salvage failed for session {session_id}: {e}")
                    related_knowledge = []
                
                dur_salvage = time.perf_counter() - t_salvage_start

                # 7. Opportunistic Recovery
                if "PYTEST_CURRENT_TEST" not in os.environ:
                    create_background_task(
                        trigger_opportunistic_recovery(), name="opportunistic_recovery"
                    )

                # 8. Final Distillation
                if not next_thought_needed:
                    from ripen.core.distiller import auto_distill_knowledge

                    try:
                        # Auto-distillation is heavier, give it 60 seconds
                        logger.info(f"Triggering final distillation for session {session_id}...")
                        await asyncio.wait_for(
                            auto_distill_knowledge(session_id, [*history, {"thought": masked_thought}]),
                            timeout=60.0
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"Final distillation timed out for session {session_id}.")
                    except Exception as e:
                        logger.error(f"Final distillation failed for session {session_id}: {e}")

                await uow.commit()

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
            from ripen.common.exceptions import DatabaseError
            logger.error(f"Critical failure in sequential thinking session {session_id}: {e}")
            raise DatabaseError(f"Reasoning persistence failed: {e}") from e


async def get_thought_history(session_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieves the thought history for a specific session."""
    session_id = session_id or "default_session"
    try:
        async with UnitOfWork(is_thoughts=True) as uow:
            return await uow.thoughts.get_session_history(session_id)
    except Exception as e:
        logger.error(f"Failed to retrieve history for session {session_id}: {e}")
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
        async with UnitOfWork(is_thoughts=True) as uow:
            all_to_process = await uow.thoughts.get_undistilled_sessions()

            if not all_to_process:
                return

            logger.info(f"Found {len(all_to_process)} undistilled sessions to recover.")
            from ripen.core.distiller import auto_distill_knowledge

            for sess_id in all_to_process:
                history = await uow.thoughts.get_session_history(sess_id)
                if history:
                    await auto_distill_knowledge(sess_id, history)
                    await uow.thoughts.mark_session_distilled(sess_id)

            await uow.commit()
    except Exception as e:
        logger.error(f"Failed during opportunistic thought recovery: {e}")
