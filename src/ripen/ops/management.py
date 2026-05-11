import json
import os
import shutil
from datetime import datetime

import numpy as np

from ripen.common.utils import (
    calculate_importance,
    get_db_path,
    get_logger,
    log_error,
)

logger = get_logger("management")


async def create_snapshot_logic(name: str, description: str, uow):
    db_path = get_db_path()
    snapshot_dir = os.path.join(os.path.dirname(db_path), "snapshots")
    if not os.path.exists(snapshot_dir):
        os.makedirs(snapshot_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = os.path.join(snapshot_dir, f"snapshot_{ts}.db")

    try:
        # Repository doesn't have vacuum, so we use uow.execute if available or raw conn
        # Let's assume Repository handles specific complex DB operations or we add it to IManagement
        await uow.management.vacuum_into(snapshot_file)
        await uow.management.insert_snapshot(name, description, snapshot_file)
        return f"Snapshot '{name}' created at {snapshot_file}"
    except Exception as e:
        log_error("Failed to create snapshot", e)
        return f"Error: Snapshot failed: {e}"


async def restore_snapshot_logic(snapshot_id: int, uow):
    try:
        row = await uow.management.get_snapshot_path(snapshot_id)
        if not row:
            return f"Error: Snapshot ID {snapshot_id} not found."

        snapshot_file = row["file_path"]
        db_path = get_db_path()
        shutil.copy2(snapshot_file, db_path)
        return f"Successfully restored database from snapshot at {snapshot_file}"
    except Exception as e:
        log_error("Failed to restore snapshot", e)
        return f"Error: Restore failed: {e}"


async def get_audit_history_logic(limit: int, table_name: str | None, uow):
    logs = await uow.audit.get_history(limit, table_name)
    return [
        {
            "id": log["id"],
            "table": log["table_name"],
            "cid": log["content_id"],
            "action": log["action"],
            "timestamp": log["timestamp"],
            "agent": log["agent_id"],
        }
        for log in logs
    ]


async def rollback_memory_logic(audit_id: int, uow):
    try:
        log = await uow.audit.get_audit_log_by_id(audit_id)
        if not log or not log.get("old_data"):
            return "Error: Audit record not found or has no 'old_data' to restore."

        table = log["table_name"]
        cid = log["content_id"]
        data = json.loads(log["old_data"])

        if table == "entities":
            await uow.entities.upsert_entity(
                data["name"], data["type"], data["desc"], data.get("importance", 5), "rollback"
            )
        elif table == "bank_files":
            await uow.bank.upsert_bank_file(cid, data["content"], "rollback")

        return f"Successfully rolled back {cid} in {table}."
    except Exception as e:
        log_error(f"Rollback failed for audit_id {audit_id}", e)
        return f"Error: Rollback failed: {e}"


async def get_memory_health_logic(uow):
    health = {}
    try:
        health["entities_count"] = await uow.management.get_count("entities")
        health["relations_count"] = await uow.management.get_count("relations")
        health["observations_count"] = await uow.management.get_count("observations")
        health["bank_files_cached"] = await uow.management.get_count("bank_files")
        health["embeddings_count"] = await uow.management.get_count("embeddings")

        metadata = await uow.metadata.get_all_metadata()
        if metadata:
            scores = [calculate_importance(m["access_count"], m["last_accessed"]) for m in metadata]
            health["importance_stats"] = {
                "avg": round(sum(scores) / len(scores), 2),
                "std_dev": round(float(np.std(scores)), 2),
                "max": round(max(scores), 2),
                "min": round(min(scores), 2),
            }
            health["archive_candidates_count"] = sum(1 for s in scores if s < 0.1)

        models = await uow.management.get_embedding_model_distribution()
        health["model_distribution"] = models

        health["missing_embeddings"] = (
            health["entities_count"] + health["bank_files_cached"] - health["embeddings_count"]
        )

        from ripen.common.config import settings

        if settings.embedding_engine == "fastembed":
            health["semantic_search_active"] = True
        else:
            from ripen.infra.embeddings import get_gemini_client

            health["semantic_search_active"] = get_gemini_client() is not None

        isolated = await uow.management.get_isolated_entities()
        health["gaps_analysis"] = {
            "isolated_entities_count": len(isolated),
            "isolated_entities": [i for i in isolated[:10]],
        }

        if health["entities_count"] > 1:
            count = health["entities_count"]
            max_relations = count * (count - 1)
            health["gaps_analysis"]["graph_density"] = round(
                health["relations_count"] / max_relations, 4
            )
        else:
            health["gaps_analysis"]["graph_density"] = 0

        health["bias_analysis"] = await uow.management.get_entity_type_distribution()
        health["agent_contribution"] = await uow.management.get_agent_contribution_stats()

    except Exception as e:
        log_error("Health diagnostics failed", e)
        health["error"] = str(e)
    return health


async def list_snapshots_logic(uow):
    rows = await uow.management.list_snapshots()
    return [{"id": r["id"], "name": r["name"], "timestamp": r["timestamp"]} for r in rows]


async def get_unresolved_conflicts_logic(uow):
    """Returns all unresolved knowledge conflicts."""
    rows = await uow.conflicts.get_unresolved_conflicts()
    return [
        {
            "id": r["id"],
            "entity": r["entity_name"],
            "existing": r["existing_content"],
            "proposed": r["new_content"],
            "reason": r["reason"],
            "agent": r["agent_id"],
            "detected_at": r["detected_at"],
        }
        for r in rows
    ]


async def resolve_conflict_logic(conflict_id: int, action: str, uow):
    """
    Resolves a conflict.
    """
    try:
        row = await uow.conflicts.get_conflict_by_id(conflict_id)
        if not row:
            return f"Error: Conflict ID {conflict_id} not found."

        entity_name, new_content, agent_id = row["entity_name"], row["new_content"], row["agent_id"]

        if action == "approve":
            await uow.observations.insert_observation(entity_name, new_content, agent_id)
            await uow.entities.increment_importance(entity_name)
            logger.info(f"Conflict {conflict_id} APPROVED and promoted to observations.")

        await uow.conflicts.mark_resolved(conflict_id)
        return f"Conflict {conflict_id} {action}ed successfully."
    except Exception as e:
        log_error(f"Failed to resolve conflict {conflict_id}", e)
        return f"Error: Resolution failed: {e}"
