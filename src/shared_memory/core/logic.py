import asyncio
import json
import time
from typing import Any

import aiosqlite

from shared_memory.common.utils import get_logger, log_error
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
    for e in entities or []:
        if isinstance(e, str):
            normalized.append({"name": e, "entity_type": "concept", "description": ""})
        elif isinstance(e, dict):
            # Ensure name exists and map common synonyms
            e["name"] = e.get("name") or e.get("id") or e.get("title")
            e["entity_type"] = e.get("entity_type") or e.get("type") or "concept"
            e["description"] = e.get("description") or e.get("desc") or e.get("content") or ""
            normalized.append(e)
    return normalized


def normalize_observation_item(obs: dict[str, Any] | str) -> dict[str, Any] | None:
    """Normalize a single observation item."""
    if isinstance(obs, str):
        return {"content": obs, "entity_name": "Global"}
    elif isinstance(obs, dict):
        # Map synonyms (Crucial: 'observation' -> 'content')
        content = obs.get("content") or obs.get("observation") or obs.get("text")
        if not content:
            return None
        entity_name = obs.get("entity_name") or obs.get("entity") or "Unknown"
        return {"content": content, "entity_name": entity_name}
    return None


def normalize_observations(observations: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    """Normalize a list of observations."""
    normalized = []
    for obs in observations or []:
        item = normalize_observation_item(obs)
        if item:
            normalized.append(item)
    return normalized


def normalize_bank_files(bank_files: Any) -> dict[str, str]:
    """
    Standardizes bank_files input into a dict[str, str].
    Handles:
    - Already a dict: { "file.md": "content" }
    - List of dicts with various naming:
        [{"filename": "a.md", "content": "..."}, {"name": "b.md", "text": "..."}]
    - List of simple dicts: [{"a.md": "content"}]
    """
    if not bank_files:
        return {}

    result = {}

    # 1. Handle Single Dictionary Case
    if isinstance(bank_files, dict):
        # Could be { "file.md": "content" } OR { "filename": "a.md", "content": "..." }
        if "content" in bank_files or "text" in bank_files:
            # It's a single file object passed as a dict
            content = bank_files.get("content") or bank_files.get("text")
            filename = (
                bank_files.get("filename") or bank_files.get("name") or "derived_knowledge.md"
            )
            if content:
                result[str(filename)] = str(content)
            return result
        # Standard format: { "file.md": "content" }
        return {str(k): str(v) for k, v in bank_files.items() if v}

    # 2. Handle List Case
    if isinstance(bank_files, list):
        for i, item in enumerate(bank_files):
            if not isinstance(item, dict):
                continue

            # Pattern A: Standard explicit keys
            # (Checks multiple synonyms for filename and content)
            filename = item.get("filename") or item.get("name") or item.get("title")
            content = item.get("content") or item.get("text") or item.get("body")

            if content:
                if not filename:
                    filename = f"derived_knowledge_{i}.md"
                result[str(filename)] = str(content)
                continue

            # Pattern B: Item is a single { "filename.md": "content" } entry
            # But only if it's not a structured dict that happens to have 1 key
            if len(item) == 1:
                key, val = next(iter(item.items()))
                # Ignore if the single key is a known attribute name but has no value
                if key in ["filename", "name", "title", "content", "text", "body"]:
                    continue
                if isinstance(val, str):
                    result[str(key)] = val
                    continue

        return result

    return {}


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
    Performs all slow AI operations outside the DB transaction.
    """
    logger.info("save_memory_core START")
    try:
        await init_db()
    except Exception as e:
        logger.exception("Critical Error: Could not initialize database")
        log_error("Critical Error: Could not initialize database", e)
        return f"Critical Error: Could not initialize database. {e}"

    # --- Normalization (Handle string shorthands and synonyms) ---
    entities = normalize_entities(entities)
    observations = normalize_observations(observations)
    relations = relations or []
    bank_files = normalize_bank_files(bank_files)

    # --- Phase 1: Pre-compute AI results ---
    start_time = time.perf_counter()
    logger.info(
        f"Phase 1 (AI) START: {len(entities)} entities, {len(relations)} relations, "
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
    logger.info(f"Prepared {len(all_embedding_texts)} embedding inputs")

    # 1.2 Prepare Tasks (Embeddings and Hashtags)
    tasks = []
    if all_embedding_texts:
        logger.debug("Adding compute_embeddings_bulk task")
        tasks.append(compute_embeddings_bulk(all_embedding_texts))
    else:
        tasks.append(asyncio.sleep(0, result=[]))

    # Add Hashtag Extraction Tasks
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
    logger.info("Phase 1.1 (Embeddings & Tags) GATHERING")
    try:
        results_gathering = await asyncio.gather(
            tasks[0],
            asyncio.gather(*hashtag_tasks)
        )
        all_vectors = results_gathering[0]
        all_extracted_tags = results_gathering[1]
    except Exception as e:
        logger.exception("Phase 1.1 FAILED (AI computation)")
        log_error("AI computation failed", e)
        return f"AI Error: AI computation failed. {e}"

    ai_duration = time.perf_counter() - ai_start_time
    logger.info(f"Phase 1.1 COMPLETE. Duration: {ai_duration:.2f}s")

    # Distribute Results
    precomputed_entity_vectors = all_vectors[: len(entity_texts)]
    precomputed_bank_vectors = all_vectors[len(entity_texts) :]

    entity_tags = all_extracted_tags[: len(entities)]
    observation_tags = all_extracted_tags[len(entities) :]

    # --- Phase 2: Sequential Write (Conflict Checks + DB Write) ---
    logger.info("Phase 2 (Protected) START")
    db_start_time = time.perf_counter()
    try:
        async with get_write_semaphore():
            # 2.1 Conflict Checks (Inside semaphore to avoid races)
            logger.info(f"Phase 2.1 (Conflict Checks) START for {len(observations)} observations")

            # Group observations by entity to minimize AI calls
            entity_groups = {}
            for i, obs in enumerate(observations):
                name = obs.get("entity_name", "Unknown")
                if name not in entity_groups:
                    entity_groups[name] = []
                entity_groups[name].append({"index": i, "content": obs.get("content", "")})

            # Create parallel tasks (one task per unique entity)
            unique_entities = list(entity_groups.keys())
            conflict_tasks = [
                graph.check_conflict(
                    entity_name, [item["content"] for item in entity_groups[entity_name]], agent_id
                )
                for entity_name in unique_entities
            ]

            # Execute all group checks in parallel
            group_results = await asyncio.gather(*conflict_tasks, return_exceptions=True)

            # Map results back to original indices
            precomputed_observations_conflicts = [None] * len(observations)
            for entity_name, result in zip(unique_entities, group_results, strict=True):
                if isinstance(result, Exception):
                    logger.error(f"Batch conflict check failed for entity {entity_name}: {result}")
                    # Strict by default: Mark as conflict on error to prevent unsafe saves
                    for item in entity_groups[entity_name]:
                        precomputed_observations_conflicts[item["index"]] = {
                            "index": item["index"],
                            "is_conflict": True,
                            "reason": f"Conflict check failed: {result}",
                        }
                else:
                    # result is a list of (is_conflict, reason) tuples
                    for item, (is_conflict, reason) in zip(
                        entity_groups[entity_name], result, strict=True
                    ):
                        precomputed_observations_conflicts[item["index"]] = {
                            "index": item["index"],
                            "is_conflict": is_conflict,
                            "reason": reason,
                        }

            # 2.2 Rapid DB Write
            async with await async_get_connection() as conn:
                logger.info("DB Connection ACQUIRED")
                results = []
                try:
                    if entities:
                        logger.info(f"Saving {len(entities)} entities...")
                        results.append(
                            await graph.save_entities(
                                entities,
                                agent_id,
                                conn,
                                precomputed_vectors=precomputed_entity_vectors,
                            )
                        )
                        # Save entity tags
                        for e, tags in zip(entities, entity_tags, strict=True):
                            await graph.save_tags(e.get("name"), "entity", tags, conn)
                    if relations:
                        logger.info(f"Saving {len(relations)} relations...")
                        results.append(await graph.save_relations(relations, agent_id, conn))
                    if observations:
                        logger.info(f"Saving {len(observations)} observations...")
                        res, conflicts = await graph.save_observations(
                            observations,
                            agent_id,
                            conn,
                            precomputed_conflicts=precomputed_observations_conflicts,
                        )
                        results.append(res)
                        # Save observation tags
                        for obs, tags in zip(observations, observation_tags, strict=True):
                            # In observation save, we don't have a stable ID until insert,
                            # but we can use entity_name + content as a proxy or just skip if no ID.
                            # Better: use content_id = hash(content) or similar if needed.
                            # For simplicity, we use entity_name as the anchor.
                            await graph.save_tags(obs.get("entity_name"), "observation", tags, conn)
                        if conflicts:
                            logger.warning(f"Conflicts detected: {len(conflicts)}")
                            results.append(f"CONFLICTS DETECTED: {json.dumps(conflicts)}")
                    if bank_files:
                        logger.info(f"Saving {len(bank_files)} bank files...")
                        results.append(
                            await bank.save_bank_files(
                                bank_files,
                                agent_id,
                                conn,
                                precomputed_vectors=precomputed_bank_vectors,
                            )
                        )

                    logger.info("Committing database transaction...")
                    await conn.commit()
                    logger.info("Database transaction COMMITTED.")
                except aiosqlite.Error as e:
                    logger.exception("DB Transaction Error")
                    await conn.rollback()
                    log_error("Database transaction failed in save_memory_core", e)
                    return f"Database Error: Transaction failed. {e}"
                except Exception as e:
                    logger.exception("Unexpected error during DB phase")
                    await conn.rollback()
                    log_error("Unexpected error in save_memory_core", e)
                    return f"Internal Error: {e}"
    except Exception as e:
        logger.exception("Critical Error: Failed to acquire DB connection")
        return f"Critical Error: Failed to acquire DB connection. {e}"

    db_duration = time.perf_counter() - db_start_time
    total_duration = time.perf_counter() - start_time
    result_summary = " | ".join(results)
    logger.info(
        f"save_memory_core SUCCESS. Results: {result_summary}. "
        f"Total: {total_duration:.2f}s (AI: {ai_duration:.2f}s, DB: {db_duration:.2f}s)"
    )
    return result_summary


async def read_memory_core(query: str | None = None) -> dict[str, Any] | str:
    """Retrieves knowledge from graph and bank."""
    start_time = time.perf_counter()
    logger.info(f"read_memory_core START query='{query}'")
    try:
        from shared_memory.infra.database import init_db

        await init_db()
    except Exception as e:
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
            return "Database Error: Database is currently locked by another process."
        return f"Database Error: Query failed. {e}"
    except Exception as e:
        log_error("Error in read_memory_core", e)
        return f"Read Error: {e}"


async def get_audit_history_core(limit: int = 20, table_name: str | None = None):
    return await management.get_audit_history_logic(limit, table_name)


async def synthesize_entity(entity_name: str):
    return await search.synthesize_knowledge(entity_name)


async def rollback_memory_core(audit_id: int):
    return await management.rollback_memory_logic(audit_id)


async def create_snapshot_core(name: str, description: str = ""):
    return await management.create_snapshot_logic(name, description)


async def restore_snapshot_core(snapshot_id: int):
    return await management.restore_snapshot_logic(snapshot_id)


async def get_memory_health_core():
    mgmt_health = await management.get_memory_health_logic()
    deep_health = await health.get_comprehensive_diagnostics()
    deep_health["management_stats"] = mgmt_health
    return deep_health


async def repair_memory_core():
    return await bank.repair_memory_logic()


async def get_value_report_core(format_type: str = "markdown"):
    """
    Returns an objective value report of the memory server.
    :param format_type: 'markdown' for human reading, 'json' for UI/API integration.
    """
    if format_type == "json":
        metrics_data = await InsightEngine.get_summary_metrics()
        return json.dumps(metrics_data, indent=2, ensure_ascii=False)

    metrics_data = await InsightEngine.get_summary_metrics()
    return InsightEngine.generate_report_markdown(metrics_data)


async def manage_knowledge_activation_core(ids: list[str], status: str):
    return await lifecycle.manage_knowledge_activation_logic(ids, status)


async def list_inactive_knowledge_core():
    return await lifecycle.list_inactive_knowledge_logic()


async def admin_run_knowledge_gc_core(age_days: int = 180, dry_run: bool = False):
    return await lifecycle.run_knowledge_gc_logic(age_days, dry_run)
