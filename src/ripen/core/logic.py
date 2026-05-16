import asyncio
import json
import time
from typing import Any

from ripen.common.utils import get_logger, normalize_text
from ripen.core import bank, graph, search
from ripen.infra.database import (
    init_db,
    retry_on_db_lock,
)
from ripen.infra.embeddings import compute_embeddings_bulk
from ripen.ops import health, lifecycle, management
from ripen.ops.insights import InsightEngine

logger = get_logger("logic")


def normalize_entities(entities: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    """Normalize entities from strings or various dict formats."""
    normalized = []
    try:
        for e in entities or []:
            if isinstance(e, str):
                normalized.append(
                    {
                        "name": normalize_text(e, truncate=255),
                        "entity_type": "concept",
                        "description": "",
                    }
                )
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
            "entity_name": normalize_text(raw_entity, truncate=255),
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


def _normalize_bank_dict(bank_files: dict) -> dict[str, str]:
    """Helper to normalize a dictionary of bank files."""
    if "content" in bank_files or "text" in bank_files:
        content = bank_files.get("content") or bank_files.get("text")
        filename = (
            bank_files.get("filename") or bank_files.get("name") or "derived_knowledge.md"
        )
        if content:
            return {str(filename): normalize_text(str(content), truncate=0)}
        return {}
    return {str(k): normalize_text(str(v), truncate=0) for k, v in bank_files.items() if v}


def _normalize_bank_list(bank_files: list) -> dict[str, str]:
    """Helper to normalize a list of bank files."""
    result = {}
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
    return result


def normalize_bank_files(bank_files: Any) -> dict[str, str]:
    """
    Standardizes bank_files input into a dict[str, str].
    Handles various input formats and synonyms.
    """
    if not bank_files:
        return {}

    try:
        if isinstance(bank_files, dict):
            return _normalize_bank_dict(bank_files)
        if isinstance(bank_files, list):
            return _normalize_bank_list(bank_files)
    except Exception as e:
        logger.error(f"Normalization failed for bank_files: {e}")
        raise

    return {}


async def _execute_memory_ai_phase(entities, observations, bank_files, local_logger):
    """Internal helper to execute the AI computation phase."""
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
    local_logger.debug(
        f"Prepared {len(all_embedding_texts)} embedding inputs "
        f"({len(entity_texts)} entities, {len(bank_texts)} bank)"
    )

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

    return {
        "entity_vectors": all_vectors[: len(entity_texts)],
        "bank_vectors": all_vectors[len(entity_texts) :],
        "entity_tags": all_extracted_tags[: len(entities)],
        "observation_tags": all_extracted_tags[len(entities) :],
        "duration": time.perf_counter() - ai_start_time,
    }


async def _handle_memory_conflicts(observations, agent_id, uow, local_logger):
    """Internal helper to batch check conflicts for observations."""
    if not observations:
        return [], 0

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
            uow=uow,
        )
        for entity_name in unique_entities
    ]
    local_logger.debug(f"Gathering {len(conflict_tasks)} conflict check tasks")
    conflict_results = await asyncio.gather(*conflict_tasks, return_exceptions=True)

    precomputed_conflicts = [None] * len(observations)
    pending_count = 0

    for entity_name, result in zip(unique_entities, conflict_results, strict=True):
        if isinstance(result, Exception):
            local_logger.error(f"Batch conflict check failed for entity {entity_name}: {result}")
            for item in entity_groups[entity_name]:
                precomputed_conflicts[item["index"]] = {
                    "index": item["index"],
                    "is_conflict": True,
                    "reason": f"Conflict check failed: {result}",
                }
                pending_count += 1
        else:
            for item, res in zip(entity_groups[entity_name], result, strict=True):
                is_conflict, reason = res
                precomputed_conflicts[item["index"]] = {
                    "index": item["index"],
                    "is_conflict": is_conflict,
                    "reason": reason,
                }
                if is_conflict:
                    pending_count += 1
    return precomputed_conflicts, pending_count


async def _perform_memory_db_write_sequence(
    uow,
    entities,
    relations,
    observations,
    bank_files,
    agent_id,
    precomputed_entity_vectors,
    precomputed_bank_vectors,
    entity_tags,
    observation_tags,
    local_logger,
):
    """Internal helper to execute the sequential DB write phase."""
    # 2.1 Conflict Checks
    local_logger.info(f"Phase 2.1 (Conflict Checks) for {len(observations)} observations")
    precomputed_obs_conflicts, pending_conflicts_count = await _handle_memory_conflicts(
        observations, agent_id, uow, local_logger
    )

    if pending_conflicts_count:
        local_logger.warning(f"Detected {pending_conflicts_count} conflicts pending review")

    # 2.2 Rapid DB Write
    local_logger.debug("Executing rapid DB write using UoW")
    results = []
    if entities:
        local_logger.info(f"Saving {len(entities)} entities...")
        results.append(
            await graph.save_entities(
                entities,
                agent_id,
                uow,
                precomputed_vectors=precomputed_entity_vectors,
            )
        )
        for e, tags in zip(entities, entity_tags, strict=True):
            await graph.save_tags(e.get("name"), "entity", tags, uow)
    if relations:
        local_logger.info(f"Saving {len(relations)} relations...")
        results.append(await graph.save_relations(relations, agent_id, uow))
    if observations:
        local_logger.info(f"Saving {len(observations)} observations...")
        res, conflicts = await graph.save_observations(
            observations,
            agent_id,
            uow,
            precomputed_conflicts=precomputed_obs_conflicts,
        )
        results.append(res)
        for obs, tags in zip(observations, observation_tags, strict=True):
            await graph.save_tags(obs.get("entity_name"), "observation", tags, uow)
        if conflicts:
            local_logger.warning(f"Conflicts detected: {len(conflicts)}")
            results.append(f"CONFLICTS DETECTED: {json.dumps(conflicts)}")
    if bank_files:
        local_logger.info(f"Saving {len(bank_files)} bank files...")
        results.append(
            await bank.save_bank_files(
                bank_files,
                agent_id,
                uow,
                precomputed_vectors=precomputed_bank_vectors,
            )
        )
    return results


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
            logger.debug("STEP 0: DB Initialization starting")
            await init_db()
            logger.debug("STEP 0: DB Initialization success")
        except Exception as e:
            local_logger.exception("CRITICAL: Database initialization failed")
            raise RuntimeError(f"Critical Error: Could not initialize database: {e}") from e

        # --- Normalization ---
        logger.debug("STEP 1: Normalization starting")
        local_logger.debug("Normalizing inputs...")
        entities = normalize_entities(entities)
        observations = normalize_observations(observations)
        relations = relations or []
        bank_files = normalize_bank_files(bank_files)
        local_logger.debug(
            f"Normalization complete: {len(entities)} entities, {len(observations)} obs"
        )

        # --- Phase 1: Pre-compute AI results ---
        logger.debug("STEP 2: Phase 1 (AI Computation) starting")
        start_time = time.perf_counter()
        ai_results = await _execute_memory_ai_phase(
            entities, observations, bank_files, local_logger
        )
        ai_duration = ai_results["duration"]
        local_logger.info(f"Phase 1.1 (AI) complete in {ai_duration:.2f}s")

        # --- Phase 2: Sequential Write ---
        local_logger.info("Phase 2 (Protected Write) started")
        db_start_time = time.perf_counter()
        try:
            from ripen.infra.uow import SecureWriteContext

            async with SecureWriteContext() as uow:
                results = await _perform_memory_db_write_sequence(
                    uow,
                    entities,
                    relations,
                    observations,
                    bank_files,
                    agent_id,
                    ai_results["entity_vectors"],
                    ai_results["bank_vectors"],
                    ai_results["entity_tags"],
                    ai_results["observation_tags"],
                    local_logger,
                )
                local_logger.debug("Committing database transaction...")
                await uow.commit()
                local_logger.info("Database transaction committed successfully")
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
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            logger.debug("STEP 1: UoW Session established")
            if query:
                logger.debug(f"STEP 2: Performing search for query: {query}")
                graph_data, bank_data = await search.perform_search(query, uow)
            else:
                # IMPORTANT: DO NOT return all data. Limit to recent 20 items.
                logger.debug("STEP 2: Listing recent memories (no query)")
                graph_data = await graph.get_graph_data(uow, limit=20)
                bank_data = await bank.read_bank_data(uow)  # Bank is also heavy

            duration = time.perf_counter() - start_time
            logger.info(f"read_memory_core COMPLETE query='{query}' duration={duration:.2f}s")
            logger.debug(
                f"STEP 3: Search results retrieved "
                f"(entities={len(graph_data.get('entities', []))})"
            )
            return {"graph": graph_data, "bank": bank_data}
    except Exception as e:
        logger.exception(f"Unexpected error in read_memory_core: {e}")
        return f"Read Error: {e}"


async def save_troubleshooting_knowledge_core(
    title: str,
    solution: str,
    affected_functions: list[str] | str | None = None,
    env_metadata: dict[str, Any] | None = None,
) -> str:
    """
    Saves high-signal troubleshooting knowledge to the premium STABLE layer.
    """
    local_logger = logger.bind(operation="save_troubleshooting")
    local_logger.info(f"Saving troubleshooting knowledge: {title}")

    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            affected = (
                json.dumps(affected_functions)
                if isinstance(affected_functions, list)
                else str(affected_functions or "")
            )
            env = json.dumps(env_metadata or {})

            await uow.troubleshooting.insert_troubleshooting(title, solution, affected, env)
            await uow.commit()
            local_logger.info("Troubleshooting knowledge saved successfully")
            return f"Successfully saved troubleshooting knowledge: {title}"
    except Exception as e:
        local_logger.exception("Failed to save troubleshooting knowledge")
        return f"Error: {e}"


async def get_audit_history_core(limit: int = 20, table_name: str | None = None):
    try:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            return await management.get_audit_history_logic(limit, table_name, uow)
    except Exception:
        logger.exception("Failed to retrieve audit history")
        raise


async def synthesize_entity(entity_name: str):
    try:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            return await search.synthesize_knowledge(entity_name, uow)
    except Exception:
        logger.exception(f"Knowledge synthesis failed for {entity_name}")
        raise


async def rollback_memory_core(audit_id: int):
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await management.rollback_memory_logic(audit_id, uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception(f"Rollback failed for audit_id {audit_id}")
        raise


async def create_snapshot_core(name: str, description: str = ""):
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await management.create_snapshot_logic(name, description, uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception(f"Snapshot creation failed: {name}")
        raise


async def restore_snapshot_core(snapshot_id: int):
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await management.restore_snapshot_logic(snapshot_id, uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception(f"Snapshot restoration failed: {snapshot_id}")
        raise


async def get_memory_health_core():
    try:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            mgmt_health = await management.get_memory_health_logic(uow)
            deep_health = await health.get_comprehensive_diagnostics(uow)
            deep_health["management_stats"] = mgmt_health
            return deep_health
    except Exception:
        logger.exception("Health diagnostics failed")
        raise


async def repair_memory_core():
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await bank.repair_memory_logic(uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception("Memory repair failed")
        raise


async def get_value_report_core(format_type: str = "markdown"):
    try:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            if format_type == "json":
                metrics_data = await InsightEngine.get_summary_metrics(uow)
                return json.dumps(metrics_data, indent=2, ensure_ascii=False)

            metrics_data = await InsightEngine.get_summary_metrics(uow)
            return InsightEngine.generate_report_markdown(metrics_data)
    except Exception:
        logger.exception("Value report generation failed")
        raise


async def manage_knowledge_activation_core(ids: list[str], status: str):
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await lifecycle.manage_knowledge_activation_logic(ids, status, uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception(f"Knowledge activation update failed for {ids}")
        raise


async def list_inactive_knowledge_core():
    try:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as uow:
            return await lifecycle.list_inactive_knowledge_logic(uow)
    except Exception:
        logger.exception("Failed to list inactive knowledge")
        raise


async def admin_run_knowledge_gc_core(age_days: int = 180, dry_run: bool = False):
    try:
        from ripen.infra.uow import SecureWriteContext

        async with SecureWriteContext() as uow:
            res = await lifecycle.run_knowledge_gc_logic(age_days, dry_run, uow)
            await uow.commit()
            return res
    except Exception:
        logger.exception("Garbage collection task failed")
        raise
