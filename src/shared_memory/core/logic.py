import asyncio
import json
import time
from typing import Any

import aiosqlite

from shared_memory.common.utils import get_logger, normalize_text
from shared_memory.core import bank, graph, search
from shared_memory.infra.database import (
    async_get_connection,
    get_write_semaphore,
    init_db,
    retry_on_db_lock,
)
from shared_memory.infra.embeddings import compute_embeddings_bulk
from shared_memory.ops import health, lifecycle, management
from shared_memory.ops.insights import InsightEngine

logger = get_logger("logic")


def normalize_entities(entities: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    """Normalize entities from strings or various dict formats."""
    normalized = []
    try:
        for e in entities or []:
            if isinstance(e, str):
                normalized.append({
                    "name": normalize_text(e, truncate=255), 
                    "entity_type": "concept", 
                    "description": ""
                })
            elif isinstance(e, dict):
                # Ensure name exists and map common synonyms
                raw_name = e.get("name") or e.get("id") or e.get("title") or "Unnamed"
                e["name"] = normalize_text(raw_name, truncate=255)
                
                raw_type = e.get("entity_type") or e.get("type") or "concept"
                e["entity_type"] = normalize_text(raw_type, truncate=100)
                
                raw_desc = e.get("description") or e.get("desc") or e.get("content") or ""
                e["description"] = normalize_text(raw_desc, truncate=5000)
                normalized.append(e)
    except Exception as e:
        logger.error(f"Normalization failed for entities: {e}")
        raise
    return normalized


def normalize_observation_item(obs: dict[str, Any] | str) -> dict[str, Any] | None:
    """Normalize a single observation item."""
    if isinstance(obs, str):
        return {"content": normalize_text(obs), "entity_name": "Global"}
    elif isinstance(obs, dict):
        # Map synonyms (Crucial: 'observation' -> 'content')
        raw_content = obs.get("content") or obs.get("observation") or obs.get("text")
        if not raw_content:
            return None
        
        raw_entity = obs.get("entity_name") or obs.get("entity") or "Unknown"
        return {
            "content": normalize_text(raw_content), 
            "entity_name": normalize_text(raw_entity, truncate=255)
        }
    return None


def normalize_observations(observations: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    """Normalize a list of observations."""
    normalized = []
    try:
        for obs in observations or []:
            item = normalize_observation_item(obs)
            if item:
                normalized.append(item)
    except Exception as e:
        logger.error(f"Normalization failed for observations: {e}")
        raise
    return normalized


def normalize_bank_files(bank_files: Any) -> dict[str, str]:
    """
    Standardizes bank_files input into a dict[str, str].
    Handles various input formats and synonyms.
    """
    if not bank_files:
        return {}

    result = {}
    try:
        # 1. Handle Single Dictionary Case
        if isinstance(bank_files, dict):
            if "content" in bank_files or "text" in bank_files:
                content = bank_files.get("content") or bank_files.get("text")
                filename = (
                    bank_files.get("filename") or bank_files.get("name") or "derived_knowledge.md"
                )
                if content:
                    result[str(filename)] = normalize_text(str(content), truncate=0) # No truncate for bank files
                return result
            return {str(k): normalize_text(str(v), truncate=0) for k, v in bank_files.items() if v}

        # 2. Handle List Case
        if isinstance(bank_files, list):
            for i, item in enumerate(bank_files):
                if not isinstance(item, dict):
                    continue

                filename = item.get("filename") or item.get("name") or item.get("title")
                content = item.get("content") or item.get("text") or item.get("body")

                if content:
                    if not filename:
                        filename = f"derived_knowledge_{i}.md"
                    result[str(filename)] = normalize_text(str(content), truncate=0)
                    continue

                if len(item) == 1:
                    key, val = next(iter(item.items()))
                    if key in ["filename", "name", "title", "content", "text", "body"]:
                        continue
                    if isinstance(val, str):
                        result[str(key)] = normalize_text(val, truncate=0)
                        continue
    except Exception as e:
        logger.error(f"Normalization failed for bank_files: {e}")
        raise

    return result


@retry_on_db_lock()
async def save_memory_core(
    entities: list[dict[str, Any] | str] | None = None,
    relations: list[dict[str, Any]] | None = None,
    observations: list[dict[str, Any] | str] | None = None,
    bank_files: dict[str, str] | list[dict[str, str]] | Any | None = None,
    agent_id: str = "default_agent",
) -> str:
    """
    Orchestrates memory saving using 'Compute-then-Write' pattern.
    """
    local_logger = logger.bind(agent_id=agent_id, operation="save_memory")
    local_logger.info("save_memory_core execution started")
    try:
        try:
            await init_db()
        except Exception as e:
            local_logger.exception("CRITICAL: Database initialization failed")
            raise RuntimeError(f"Critical Error: Could not initialize database: {e}") from e

        # --- Normalization ---
        entities = normalize_entities(entities)
        observations = normalize_observations(observations)
        relations = relations or []
        bank_files = normalize_bank_files(bank_files)

        # --- Phase 1: Pre-compute AI results ---
        start_time = time.perf_counter()
        local_logger.info(
            "Phase 1 (AI Computation) started: "
            f"{len(entities)} entities, {len(relations)} relations, "
            f"{len(observations)} observations, {len(bank_files)} bank files"
        )
        ai_start_time = time.perf_counter()

        # 1.1 Prepare Embedding Inputs
        entity_texts = []
        for e in entities:
            if not e.get("name"):
                continue
            name = e.get("name")
            e_type = e.get("entity_type", "concept")
            desc = e.get("description", "")
            entity_texts.append(f"{name} ({e_type}): {desc}")

        bank_file_items = []
        for filename, content in bank_files.items():
            bank_file_items.append(
                {"filename": filename, "text": f"File: {filename}\nContent: {content}"}
            )

        bank_texts = [item["text"] for item in bank_file_items]
        all_embedding_texts = entity_texts + bank_texts
        local_logger.debug(f"Prepared {len(all_embedding_texts)} embedding inputs")

        # 1.2 Prepare Tasks
        tasks = []
        if all_embedding_texts:
            local_logger.debug("Scheduling compute_embeddings_bulk")
            tasks.append(compute_embeddings_bulk(all_embedding_texts))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        hashtag_tasks = []
        for e in entities:
            desc = e.get("description", "")
            if len(desc) > 10:
                hashtag_tasks.append(graph.extract_hashtags(f"{e.get('name')}: {desc}"))
            else:
                hashtag_tasks.append(asyncio.sleep(0, result=[]))

        for obs in observations:
            content = obs.get("content", "")
            if len(content) > 10:
                hashtag_tasks.append(graph.extract_hashtags(content))
            else:
                hashtag_tasks.append(asyncio.sleep(0, result=[]))

        # 1.3 Execute Parallel AI Calls
        local_logger.debug(f"Gathering {len(tasks) + len(hashtag_tasks)} AI tasks")
        try:
            results_gathering = await asyncio.gather(tasks[0], asyncio.gather(*hashtag_tasks))
            all_vectors = results_gathering[0]
            all_extracted_tags = results_gathering[1]
        except Exception as e:
            local_logger.exception("Phase 1.1 FAILED (AI computation)")
            raise RuntimeError(f"AI Error: AI computation failed: {e}") from e

        ai_duration = time.perf_counter() - ai_start_time
        local_logger.info(f"Phase 1.1 (AI) complete in {ai_duration:.2f}s")

        precomputed_entity_vectors = all_vectors[: len(entity_texts)]
        precomputed_bank_vectors = all_vectors[len(entity_texts) :]

        entity_tags = all_extracted_tags[: len(entities)]
        observation_tags = all_extracted_tags[len(entities) :]

        # --- Phase 2: Sequential Write ---
        local_logger.info("Phase 2 (Protected Write) started")
        db_start_time = time.perf_counter()
        try:
            async with get_write_semaphore():
                # 2.1 Conflict Checks
                local_logger.info(
                    f"Phase 2.1 (Conflict Checks) for {len(observations)} observations"
                )

                entity_groups = {}
                for i, obs in enumerate(observations):
                    name = obs.get("entity_name", "Unknown")
                    if name not in entity_groups:
                        entity_groups[name] = []
                    entity_groups[name].append({"index": i, "content": obs.get("content", "")})

                unique_entities = list(entity_groups.keys())
                conflict_tasks = [
                    graph.check_conflict(
                        entity_name,
                        [item["content"] for item in entity_groups[entity_name]],
                        agent_id,
                    )
                    for entity_name in unique_entities
                ]
                local_logger.debug(f"Gathering {len(conflict_tasks)} conflict check tasks")
                conflict_results = await asyncio.gather(*conflict_tasks, return_exceptions=True)

                precomputed_observations_conflicts = [None] * len(observations)
                pending_conflicts_count = 0

                for entity_name, result in zip(unique_entities, conflict_results, strict=True):
                    if isinstance(result, Exception):
                        local_logger.error(
                            f"Batch conflict check failed for entity {entity_name}: {result}"
                        )
                        for item in entity_groups[entity_name]:
                            precomputed_observations_conflicts[item["index"]] = {
                                "index": item["index"],
                                "is_conflict": True,
                                "reason": f"Conflict check failed: {result}",
                            }
                            pending_conflicts_count += 1
                    else:
                        for item, res in zip(entity_groups[entity_name], result, strict=True):
                            is_conflict, reason = res
                            precomputed_observations_conflicts[item["index"]] = {
                                "index": item["index"],
                                "is_conflict": is_conflict,
                                "reason": reason,
                            }
                            if is_conflict:
                                pending_conflicts_count += 1

                if pending_conflicts_count:
                    local_logger.warning(
                        f"Detected {pending_conflicts_count} conflicts pending review"
                    )

                # 2.2 Rapid DB Write
                async with await async_get_connection() as conn:
                    local_logger.debug("Database connection acquired for Phase 2.2")
                    results = []
                    try:
                        if entities:
                            local_logger.info(f"Saving {len(entities)} entities...")
                            results.append(
                                await graph.save_entities(
                                    entities,
                                    agent_id,
                                    conn,
                                    precomputed_vectors=precomputed_entity_vectors,
                                )
                            )
                            for e, tags in zip(entities, entity_tags, strict=True):
                                await graph.save_tags(e.get("name"), "entity", tags, conn)
                        if relations:
                            local_logger.info(f"Saving {len(relations)} relations...")
                            results.append(await graph.save_relations(relations, agent_id, conn))
                        if observations:
                            local_logger.info(f"Saving {len(observations)} observations...")
                            res, conflicts = await graph.save_observations(
                                observations,
                                agent_id,
                                conn,
                                precomputed_conflicts=precomputed_observations_conflicts,
                            )
                            results.append(res)
                            for obs, tags in zip(observations, observation_tags, strict=True):
                                await graph.save_tags(
                                    obs.get("entity_name"), "observation", tags, conn
                                )
                            if conflicts:
                                local_logger.warning(f"Conflicts detected: {len(conflicts)}")
                                results.append(f"CONFLICTS DETECTED: {json.dumps(conflicts)}")
                        if bank_files:
                            local_logger.info(f"Saving {len(bank_files)} bank files...")
                            results.append(
                                await bank.save_bank_files(
                                    bank_files,
                                    agent_id,
                                    conn,
                                    precomputed_vectors=precomputed_bank_vectors,
                                )
                            )

                        local_logger.debug("Committing database transaction...")
                        await conn.commit()
                        local_logger.info("Database transaction committed successfully")
                    except aiosqlite.Error as e:
                        local_logger.exception("DB Transaction Error")
                        await conn.rollback()
                        raise RuntimeError(f"Database Error: Transaction failed: {e}") from e
                    except Exception as e:
                        local_logger.exception("Unexpected error during DB phase")
                        await conn.rollback()
                        raise RuntimeError(f"Internal Error during database write: {e}") from e
        except Exception as e:
            local_logger.exception("Critical Error in Phase 2 (Protected Write)")
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Critical Error: Failed to execute protected write: {e}") from e

        db_duration = time.perf_counter() - db_start_time
        total_duration = time.perf_counter() - start_time
        result_summary = " | ".join(results)
        local_logger.info(
            f"save_memory_core success: {result_summary} "
            f"(Total: {total_duration:.2f}s, AI: {ai_duration:.2f}s, DB: {db_duration:.2f}s)"
        )
        return result_summary
    except Exception as e:
        local_logger.exception("Unhandled error in save_memory_core")
        return f"Unexpected Error: {e}"


async def read_memory_core(query: str | None = None) -> dict[str, Any] | str:
    """Retrieves knowledge from graph and bank."""
    start_time = time.perf_counter()
    logger.info(f"read_memory_core START query='{query}'")
    try:
        await init_db()
    except Exception as e:
        logger.exception("Database initialization failed in read_memory_core")
        return f"Database Error: Initialization failed. {e}"

    try:
        if query:
            graph_data, bank_data = await search.perform_search(query)
        else:
            graph_data = await graph.get_graph_data()
            bank_data = await bank.read_bank_data()

        duration = time.perf_counter() - start_time
        logger.info(f"read_memory_core COMPLETE query='{query}' duration={duration:.2f}s")
        return {"graph": graph_data, "bank": bank_data}
    except aiosqlite.OperationalError as e:
        if "locked" in str(e).lower():
            logger.warning("Database locked during read_memory_core")
            return "Database Error: Database is currently locked by another process."
        logger.exception(f"Query failed in read_memory_core: {e}")
        return f"Database Error: Query failed. {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in read_memory_core: {e}")
        return f"Read Error: {e}"


async def get_audit_history_core(limit: int = 20, table_name: str | None = None):
    try:
        return await management.get_audit_history_logic(limit, table_name)
    except Exception:
        logger.exception("Failed to retrieve audit history")
        raise


async def synthesize_entity(entity_name: str):
    try:
        return await search.synthesize_knowledge(entity_name)
    except Exception:
        logger.exception(f"Knowledge synthesis failed for {entity_name}")
        raise


async def rollback_memory_core(audit_id: int):
    try:
        return await management.rollback_memory_logic(audit_id)
    except Exception:
        logger.exception(f"Rollback failed for audit_id {audit_id}")
        raise


async def create_snapshot_core(name: str, description: str = ""):
    try:
        return await management.create_snapshot_logic(name, description)
    except Exception:
        logger.exception(f"Snapshot creation failed: {name}")
        raise


async def restore_snapshot_core(snapshot_id: int):
    try:
        return await management.restore_snapshot_logic(snapshot_id)
    except Exception:
        logger.exception(f"Snapshot restoration failed: {snapshot_id}")
        raise


async def get_memory_health_core():
    try:
        mgmt_health = await management.get_memory_health_logic()
        deep_health = await health.get_comprehensive_diagnostics()
        deep_health["management_stats"] = mgmt_health
        return deep_health
    except Exception:
        logger.exception("Health diagnostics failed")
        raise


async def repair_memory_core():
    try:
        return await bank.repair_memory_logic()
    except Exception:
        logger.exception("Memory repair failed")
        raise


async def get_value_report_core(format_type: str = "markdown"):
    try:
        if format_type == "json":
            metrics_data = await InsightEngine.get_summary_metrics()
            return json.dumps(metrics_data, indent=2, ensure_ascii=False)

        metrics_data = await InsightEngine.get_summary_metrics()
        return InsightEngine.generate_report_markdown(metrics_data)
    except Exception:
        logger.exception("Value report generation failed")
        raise


async def manage_knowledge_activation_core(ids: list[str], status: str):
    try:
        return await lifecycle.manage_knowledge_activation_logic(ids, status)
    except Exception:
        logger.exception(f"Knowledge activation update failed for {ids}")
        raise


async def list_inactive_knowledge_core():
    try:
        return await lifecycle.list_inactive_knowledge_logic()
    except Exception:
        logger.exception("Failed to list inactive knowledge")
        raise


async def admin_run_knowledge_gc_core(age_days: int = 180, dry_run: bool = False):
    try:
        return await lifecycle.run_knowledge_gc_logic(age_days, dry_run)
    except Exception:
        logger.exception("Garbage collection task failed")
        raise
