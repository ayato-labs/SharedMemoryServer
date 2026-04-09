import datetime
import json
import os
import shutil

import numpy as np

from shared_memory.database import async_get_connection
from shared_memory.embeddings import get_gemini_client
from shared_memory.utils import calculate_importance, get_db_path, log_error


async def create_snapshot_logic(name: str, description: str = ""):
    db_path = get_db_path()
    snapshot_dir = os.path.join(os.path.dirname(db_path), "snapshots")
    if not os.path.exists(snapshot_dir):
        os.makedirs(snapshot_dir)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = os.path.join(snapshot_dir, f"snapshot_{ts}.db")

    try:
        shutil.copy2(db_path, snapshot_file)
        async with await async_get_connection() as conn:
            await conn.execute(
                "INSERT INTO snapshots (name, description, file_path) VALUES (?, ?, ?)",
                (name, description, snapshot_file),
            )
            await conn.commit()
        return f"Snapshot '{name}' created at {snapshot_file}"
    except Exception as e:
        log_error("Failed to create snapshot", e)
        return f"Error: Snapshot failed: {e}"


async def restore_snapshot_logic(snapshot_id: int):
    async with await async_get_connection() as conn:
        try:
            cursor = await conn.execute(
                "SELECT file_path FROM snapshots WHERE id = ?", (snapshot_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return f"Error: Snapshot ID {snapshot_id} not found."

            snapshot_file = row[0]
            db_path = get_db_path()
            shutil.copy2(snapshot_file, db_path)
            return f"Successfully restored database from snapshot at {snapshot_file}"
        except Exception as e:
            log_error("Failed to restore snapshot", e)
            return f"Error: Restore failed: {e}"


async def get_audit_history_logic(limit: int = 20, table_name: str | None = None):
    async with await async_get_connection() as conn:
        if table_name:
            cursor = await conn.execute(
                "SELECT * FROM audit_logs WHERE table_name = ? ORDER BY timestamp DESC LIMIT ?",
                (table_name, limit),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        logs = await cursor.fetchall()

        return [
            {
                "id": log_entry[0],
                "table": log_entry[1],
                "cid": log_entry[2],
                "action": log_entry[3],
                "timestamp": log_entry[6],
                "agent": log_entry[7],
            }
            for log_entry in logs
        ]


async def rollback_memory_logic(audit_id: int):
    async with await async_get_connection() as conn:
        try:
            cursor = await conn.execute(
                "SELECT table_name, content_id, old_data FROM audit_logs WHERE id = ?",
                (audit_id,),
            )
            log = await cursor.fetchone()
            if not log or not log[2]:
                return "Error: Audit record not found or has no 'old_data' to restore."

            table, cid, data_raw = log
            data = json.loads(data_raw)

            if table == "entities":
                await conn.execute(
                    "INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)",
                    (data["name"], data["type"], data["desc"]),
                )
            elif table == "bank_files":
                await conn.execute(
                    "INSERT OR REPLACE INTO bank_files (filename, content, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (cid, data["content"]),
                )

            await conn.commit()
            return f"Successfully rolled back {cid} in {table}."
        except Exception as e:
            log_error(f"Rollback failed for audit_id {audit_id}", e)
            return f"Error: Rollback failed: {e}"


async def get_memory_health_logic():
    async with await async_get_connection() as conn:
        health = {}
        try:
            health["entities_count"] = (await (await conn.execute("SELECT COUNT(*) FROM entities")).fetchone())[0]
            health["relations_count"] = (await (await conn.execute("SELECT COUNT(*) FROM relations")).fetchone())[0]
            health["observations_count"] = (await (await conn.execute("SELECT COUNT(*) FROM observations")).fetchone())[0]
            health["bank_files_cached"] = (await (await conn.execute("SELECT COUNT(*) FROM bank_files")).fetchone())[0]
            health["embeddings_count"] = (await (await conn.execute("SELECT COUNT(*) FROM embeddings")).fetchone())[0]

            cursor = await conn.execute(
                "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
            )
            metadata = await cursor.fetchall()
            if metadata:
                scores = [calculate_importance(m[1], m[2]) for m in metadata]
                health["importance_stats"] = {
                    "avg": round(sum(scores) / len(scores), 2),
                    "std_dev": round(float(np.std(scores)), 2),
                    "max": round(max(scores), 2),
                    "min": round(min(scores), 2),
                }
                health["archive_candidates_count"] = sum(1 for s in scores if s < 0.1)

            cursor = await conn.execute(
                "SELECT model_name, COUNT(*) FROM embeddings GROUP BY model_name"
            )
            models = await cursor.fetchall()
            health["model_distribution"] = {m[0]: m[1] for m in models}

            # Check for missing embeddings
            health["missing_embeddings"] = (
                health["entities_count"]
                + health["bank_files_cached"]
                - health["embeddings_count"]
            )

            health["semantic_search_active"] = get_gemini_client() is not None

            # Gaps & Bias
            cursor = await conn.execute("""
                SELECT name FROM entities 
                WHERE name NOT IN (SELECT source FROM relations) 
                AND name NOT IN (SELECT target FROM relations)
            """)
            isolated = await cursor.fetchall()
            health["gaps_analysis"] = {
                "isolated_entities_count": len(isolated),
                "isolated_entities": [i[0] for i in isolated[:10]],
            }

            if health["entities_count"] > 1:
                max_relations = health["entities_count"] * (health["entities_count"] - 1)
                health["gaps_analysis"]["graph_density"] = round(
                    health["relations_count"] / max_relations, 4
                )
            else:
                health["gaps_analysis"]["graph_density"] = 0

            cursor = await conn.execute(
                "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
            )
            type_dist = await cursor.fetchall()
            health["bias_analysis"] = {t[0]: t[1] for t in type_dist}

            cursor = await conn.execute(
                "SELECT created_by, COUNT(*) FROM entities GROUP BY created_by"
            )
            agent_stats = await cursor.fetchall()
            health["agent_contribution"] = {
                a[0] if a[0] else "legacy": a[1] for a in agent_stats
            }

        except Exception as e:
            log_error("Health diagnostics failed", e)
            health["error"] = str(e)
        return health
async def list_snapshots_logic():
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, name, timestamp FROM snapshots ORDER BY timestamp DESC"
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "name": r[1], "timestamp": r[2]} for r in rows]
