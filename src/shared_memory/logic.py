import asyncio
import json
from typing import Any

import aiosqlite

from shared_memory import bank, graph, health, management, search
from shared_memory.insights import InsightEngine
from shared_memory.database import async_get_connection, retry_on_db_lock
from shared_memory.embeddings import compute_embeddings_bulk
from shared_memory.exceptions import DatabaseError, SharedMemoryError
from shared_memory.utils import log_error


@retry_on_db_lock()
async def save_memory_core(
    entities: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    observations: list[dict[str, Any]] | None = None,
    bank_files: dict[str, str] | None = None,
    agent_id: str = "default_agent",
) -> str:
    """
    Orchestrates memory saving using 'Compute-then-Write' pattern.
    Performs all slow AI operations outside the DB transaction.
    """
    entities = entities or []
    relations = relations or []
    observations = observations or []
    bank_files = bank_files or {}

    # --- Phase 1: Pre-compute AI results ---

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
        bank_file_items.append({
            "filename": filename,
            "text": f"File: {filename}\nContent: {content}"
        })

    bank_texts = [item["text"] for item in bank_file_items]
    all_embedding_texts = entity_texts + bank_texts

    # 1.2 Prepare Tasks (Embeddings and Conflict Checks)
    tasks = []
    if all_embedding_texts:
        tasks.append(compute_embeddings_bulk(all_embedding_texts))
    else:
        tasks.append(asyncio.sleep(0, result=[])) # Dummy task

    for obs in observations:
        tasks.append(graph.check_conflict(
            obs.get("entity_name", ""),
            obs.get("content", ""),
            agent_id
        ))

    # 1.3 Execute Parallel AI Calls
    ai_results = await asyncio.gather(*tasks)

    all_vectors = ai_results[0]
    raw_conflict_results = ai_results[1:]

    # 1.4 Distribute Results
    precomputed_entity_vectors = all_vectors[:len(entity_texts)]
    precomputed_bank_vectors = all_vectors[len(entity_texts):]

    precomputed_observations_conflicts = []
    for i, res in enumerate(raw_conflict_results):
        is_conflict, reason = res
        precomputed_observations_conflicts.append({
            "index": i,
            "is_conflict": is_conflict,
            "reason": reason
        })

    # --- Phase 2: Rapid DB Write ---

    async with await async_get_connection() as conn:
        results = []
        try:
            if entities:
                results.append(await graph.save_entities(
                    entities,
                    agent_id,
                    conn,
                    precomputed_vectors=precomputed_entity_vectors
                ))
            if relations:
                results.append(await graph.save_relations(relations, agent_id, conn))
            if observations:
                res, conflicts = await graph.save_observations(
                    observations,
                    agent_id,
                    conn,
                    precomputed_conflicts=precomputed_observations_conflicts
                )
                results.append(res)
                if conflicts:
                    results.append(
                        f"CONFLICTS DETECTED: {json.dumps(conflicts)}"
                    )
            if bank_files:
                results.append(await bank.save_bank_files(
                    bank_files,
                    agent_id,
                    conn,
                    precomputed_vectors=precomputed_bank_vectors
                ))

            await conn.commit()
        except aiosqlite.Error as e:
            await conn.rollback()
            log_error("Database transaction failed in save_memory_core", e)
            raise DatabaseError(f"Transaction failed: {e}") from e
        except Exception as e:
            await conn.rollback()
            log_error("Unexpected error in save_memory_core", e)
            raise SharedMemoryError(f"Unexpected error: {e}") from e

    return " | ".join(results)


@retry_on_db_lock()
async def read_memory_core(query: str | None = None) -> dict[str, Any]:
    """
    Core logic for reading memory.
    """
    try:
        if query:
            graph_data, bank_data = await search.perform_search(query)
        else:
            graph_data = await graph.get_graph_data()
            bank_data = await bank.read_bank_data()
        return {"graph": graph_data, "bank": bank_data}
    except Exception as e:
        log_error("Error in read_memory_core", e)
        raise SharedMemoryError(f"Read failed: {e}") from e


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
        return await InsightEngine.get_summary_metrics()

    metrics_data = await InsightEngine.get_summary_metrics()
    return InsightEngine.generate_report_markdown(metrics_data)
