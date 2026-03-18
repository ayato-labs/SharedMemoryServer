import os
import aiofiles
import pickle
import numpy as np
import math
from typing import List, Optional, Dict
from fastmcp import FastMCP

import json
try:
    from .utils import log_error, get_bank_dir, mask_sensitive_data
    from .database import get_connection, init_db, update_access
    from .logic import batch_cosine_similarity, calculate_importance
    from .embeddings import get_gemini_client, compute_embedding, EMBEDDING_MODEL
except (ImportError, ValueError):
    import sys
    import os
    # Ensure package directory is in sys.path for direct execution
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
    from utils import log_error, get_bank_dir, mask_sensitive_data
    from database import get_connection, init_db, update_access
    from logic import batch_cosine_similarity, calculate_importance
    from embeddings import get_gemini_client, compute_embedding, EMBEDDING_MODEL

mcp = FastMCP("SharedMemoryServer")

# --- MEMORY BANK STORAGE (Markdown) ---
BANK_FILES = {
    "projectBrief.md": "Core requirements and goals.",
    "productContext.md": "Why this project exists and its scope.",
    "activeContext.md": "What we are working on now and recent decisions.",
    "systemPatterns.md": "Architecture, design patterns, and technical decisions.",
    "techContext.md": "Tech stack, dependencies, and constraints.",
    "progress.md": "Status, roadmap, and what's next.",
    "decisionLog.md": "Record of significant technical choices.",
}


async def initialize_bank():
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    for filename, description in BANK_FILES.items():
        path = os.path.join(bank_dir, filename)
        if not os.path.exists(path):
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(
                    f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n"
                )


# --- UNIFIED TOOLS (V2 API) ---


@mcp.tool()
async def save_memory(
    entities: Optional[List[Dict[str, str]]] = None,
    relations: Optional[List[Dict[str, str]]] = None,
    observations: Optional[List[Dict[str, str]]] = None,
    bank_files: Optional[Dict[str, str]] = None,
    agent_id: str = "default_agent",
):
    """
    Unified write tool for both Knowledge Graph and Memory Bank.
    - agent_id: ID of the agent making the changes (for attribution)
    """
    results = []
    conn = get_connection()
    try:
        if entities:
            for e in entities:
                name = mask_sensitive_data(e["name"])
                desc = mask_sensitive_data(e.get("description", ""))

                # Audit: Get old state
                old_row = conn.execute(
                    "SELECT name, entity_type, description FROM entities WHERE name = ?",
                    (name,),
                ).fetchone()
                old_data = (
                    json.dumps(
                        {"name": old_row[0], "type": old_row[1], "desc": old_row[2]}
                    )
                    if old_row
                    else None
                )

                if old_row:
                    conn.execute(
                        "UPDATE entities SET entity_type = ?, description = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE name = ?",
                        (e["entity_type"], desc, agent_id, name),
                    )
                else:
                    conn.execute(
                        "INSERT INTO entities (name, entity_type, description, created_by, updated_by) VALUES (?, ?, ?, ?, ?)",
                        (name, e["entity_type"], desc, agent_id, agent_id),
                    )

                # Record Audit
                new_data = json.dumps(
                    {"name": name, "type": e["entity_type"], "desc": desc}
                )
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "entities",
                        name,
                        "UPDATE" if old_row else "INSERT",
                        old_data,
                        new_data,
                        agent_id,
                    ),
                )
                # Semantic segment
                vector = await compute_embedding(
                    f"{e['name']} ({e['entity_type']}): {e.get('description', '')}"
                )
                if vector:
                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                        (e["name"], pickle.dumps(vector), EMBEDDING_MODEL),
                    )
            results.append(f"Saved {len(entities)} entities (with embeddings)")

        if relations:
            relation_tuples = [
                (r["source"], r["target"], r["relation_type"], agent_id)
                for r in relations
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO relations (source, target, relation_type, created_by) VALUES (?, ?, ?, ?)",
                relation_tuples,
            )
            results.append(f"Saved {len(relations)} relations")

        if observations:
            for o in observations:
                content = mask_sensitive_data(o["content"])
                conn.execute(
                    "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
                    (o["entity_name"], content, agent_id),
                )
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, new_data, agent_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        "observations",
                        o["entity_name"],
                        "INSERT",
                        json.dumps({"content": content}),
                        agent_id,
                    ),
                )
            results.append(f"Saved {len(observations)} observations")

        if bank_files:
            # Implicit Mention Detection
            existing_entities = [
                row[0] for row in conn.execute("SELECT name FROM entities").fetchall()
            ]
            for filename, content in bank_files.items():
                if not filename.endswith(".md"):
                    filename += ".md"

                content = mask_sensitive_data(content)

                # Audit
                old_content = conn.execute(
                    "SELECT content FROM bank_files WHERE filename = ?", (filename,)
                ).fetchone()
                old_data = (
                    json.dumps({"content": old_content[0]}) if old_content else None
                )

                conn.execute(
                    "INSERT OR REPLACE INTO bank_files (filename, content, last_synced, updated_by) VALUES (?, ?, CURRENT_TIMESTAMP, ?)",
                    (filename, content, agent_id),
                )

                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "bank_files",
                        filename,
                        "UPDATE" if old_content else "INSERT",
                        old_data,
                        json.dumps({"content": content}),
                        agent_id,
                    ),
                )

                # Scan for mentions
                for entity_name in existing_entities:
                    if entity_name.lower() in content.lower():
                        conn.execute(
                            "INSERT OR REPLACE INTO relations (source, target, relation_type, justification, created_by) VALUES (?, ?, ?, ?, ?)",
                            (
                                filename,
                                entity_name,
                                "mentions",
                                f"Auto-detected in {filename}",
                                agent_id,
                            ),
                        )

                # Semantic segment
                vector = await compute_embedding(
                    f"File: {filename}\nContent:\n{content}"
                )
                if vector:
                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                        (filename, pickle.dumps(vector), EMBEDDING_MODEL),
                    )
            results.append(
                f"Mirrored {len(bank_files)} bank files and checked for implicit mentions"
            )

        conn.commit()
    except Exception as e:
        log_error("Failed to save memory to database", e)
        results.append(f"Error: DB save failed: {e}")
    finally:
        conn.close()

    if bank_files:
        bank_dir = get_bank_dir()
        file_count = 0
        for filename, content in bank_files.items():
            if not filename.endswith(".md"):
                filename += ".md"
            path = os.path.join(bank_dir, filename)

            # Masked content should be used for disk write as well
            masked_content = mask_sensitive_data(content)
            try:
                async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                    await f.write(masked_content)
                file_count += 1
            except Exception as e:
                log_error(f"Failed to write {filename} to disk", e)
                results.append(f"Warning: Failed to write {filename} to disk: {e}")
        if file_count:
            results.append(f"Updated {file_count} bank files on disk")

    return " | ".join(results) if results else "No data provided."


@mcp.tool()
async def read_memory(query: Optional[str] = None, scope: str = "all"):
    """
    Unified read tool for both Knowledge Graph and Memory Bank.
    - query: Search term (optional)
    - scope: "all", "graph", or "bank"
    """
    response = {}

    # 1. READ GRAPH
    if scope in ["all", "graph"]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if query:
                q = f"%{query}%"
                e_matches = cursor.execute(
                    "SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?",
                    (q, q),
                )
                e_rows = e_matches.fetchall()

                o_matches = cursor.execute(
                    "SELECT * FROM observations WHERE content LIKE ?", (q,)
                ).fetchall()
                for row in e_rows:
                    update_access(row[0])
                # 1-hop Graph Expansion
                matched_names = [r[0] for r in e_rows]
                if matched_names:
                    # Find all relations connected to matched entities
                    placeholders = ",".join(["?"] * len(matched_names))
                    relations = cursor.execute(
                        f"SELECT * FROM relations WHERE source IN ({placeholders}) OR target IN ({placeholders})",
                        matched_names + matched_names,
                    ).fetchall()

                    # Collect connected entities not already matched
                    connected_names = set()
                    for r in relations:
                        if r[0] not in matched_names:
                            connected_names.add(r[0])
                        if r[1] not in matched_names:
                            connected_names.add(r[1])

                    if connected_names:
                        c_placeholders = ",".join(["?"] * len(connected_names))
                        c_entities = cursor.execute(
                            f"SELECT * FROM entities WHERE name IN ({c_placeholders})",
                            list(connected_names),
                        ).fetchall()
                        c_obs = cursor.execute(
                            f"SELECT * FROM observations WHERE entity_name IN ({c_placeholders})",
                            list(connected_names),
                        ).fetchall()

                        # Merge into response
                        all_entities = e_rows + c_entities
                        all_obs = o_matches + c_obs
                    else:
                        all_entities = e_rows
                        all_obs = o_matches
                else:
                    all_entities = e_rows
                    all_obs = o_matches
                    relations = []

                response["graph"] = {
                    "entities": [
                        {"name": r[0], "type": r[1], "description": r[2]}
                        for r in all_entities
                    ],
                    "relations": [
                        {
                            "source": r[0],
                            "target": r[1],
                            "type": r[2],
                            "justification": r[3],
                        }
                        for r in relations
                    ],
                    "observations": [
                        {"entity": o[1], "content": o[2], "at": o[3]} for o in all_obs
                    ],
                }
            else:
                entities = cursor.execute("SELECT * FROM entities").fetchall()
                relations = cursor.execute("SELECT * FROM relations").fetchall()
                obs = cursor.execute("SELECT * FROM observations").fetchall()
                response["graph"] = {
                    "entities": [
                        {"name": e[0], "type": e[1], "description": e[2]}
                        for e in entities
                    ],
                    "relations": [
                        {
                            "source": r[0],
                            "target": r[1],
                            "type": r[2],
                            "justification": r[3],
                        }
                        for r in relations
                    ],
                    "observations": [
                        {"entity": o[1], "content": o[2], "at": o[3]} for o in obs
                    ],
                }
        except Exception as e:
            log_error("Failed to read knowledge graph", e)
            response["graph_error"] = str(e)
        finally:
            conn.close()

    # 2. READ BANK (with DB recovery)
    if scope in ["all", "bank"]:
        bank_dir = get_bank_dir()
        bank_data = {}
        found_files = set()

        # Try reading from physical disk first
        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".md"):
                    path = os.path.join(bank_dir, filename)
                    try:
                        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                            content = await f.read()
                            if not query or query.lower() in content.lower():
                                bank_data[filename] = content
                                found_files.add(filename)
                                update_access(filename)
                    except Exception as e:
                        log_error(f"Failed to read bank file {filename}", e)

        # Fallback/Supplemental: Read from DB mirror
        conn = get_connection()
        try:
            cursor = conn.cursor()
            db_files = cursor.execute(
                "SELECT filename, content FROM bank_files"
            ).fetchall()
            for filename, content in db_files:
                if filename not in found_files:
                    if not query or query.lower() in content.lower():
                        bank_data[f"{filename} [RECOVERED]"] = content
        except Exception as e:
            log_error("Failed to read bank/mirror from database", e)
        finally:
            conn.close()

        response["bank"] = bank_data

    # 3. SEMANTIC SEARCH (Hybrid Reranking with Batching Optimization)
    if query and get_gemini_client():
        query_vector = await compute_embedding(query)
        if query_vector:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                rows = cursor.execute(
                    "SELECT content_id, vector, model_name FROM embeddings"
                ).fetchall()
                if rows:
                    cids = [r[0] for r in rows]
                    vectors = np.array([pickle.loads(r[1]) for r in rows])
                    scores = batch_cosine_similarity(query_vector, vectors)

                    semantic_results = list(zip(cids, scores))

                    # Get importance scores and stability
                    metadata = cursor.execute(
                        "SELECT content_id, access_count, last_accessed, stability FROM knowledge_metadata"
                    ).fetchall()
                    importance_map = {
                        m[0]: calculate_importance(m[1], m[2], m[3]) for m in metadata
                    }

                    # Associative Priming: Boost neighbors of matched entities
                    primed_ids = set()
                    if "graph" in response and "relations" in response["graph"]:
                        for rel in response["graph"]["relations"]:
                            # If source or target is a strong semantic hit, prime the other
                            primed_ids.add(rel["source"])
                            primed_ids.add(rel["target"])

                    # Hybrid ranking: Similarity * Importance (+ Priming Boost)
                    hybrid_results = []
                    for cid, score in semantic_results:
                        imp_weight = importance_map.get(cid, 1.1)
                        # Priming boost: +20% importance if the item is related to a direct hit
                        prime_boost = 1.2 if cid in primed_ids else 1.0

                        final_score = (
                            score * (0.8 + 0.2 * math.log1p(imp_weight)) * prime_boost
                        )
                        hybrid_results.append(
                            (cid, final_score, score, imp_weight, cid in primed_ids)
                        )

                    hybrid_results.sort(key=lambda x: x[1], reverse=True)
                    response["semantic_hits"] = [
                        {
                            "id": r[0],
                            "score": round(float(r[1]), 4),
                            "base_similarity": round(float(r[2]), 4),
                            "importance": round(r[3], 2),
                            "primed": r[4],
                        }
                        for r in hybrid_results[:5]
                        if r[2] > 0.3
                    ]
            except Exception as e:
                log_error("Semantic search computation failed", e)
            finally:
                conn.close()

    return response


@mcp.tool()
def delete_memory(entities: List[str], agent_id: str = "default_agent"):
    """Removes specific entities and their associated data from the Knowledge Graph."""
    conn = get_connection()
    try:
        for name in entities:
            # Audit: Save old state before deletion
            old_row = conn.execute(
                "SELECT name, entity_type, description FROM entities WHERE name = ?",
                (name,),
            ).fetchone()
            if old_row:
                old_data = json.dumps(
                    {"name": old_row[0], "type": old_row[1], "desc": old_row[2]}
                )
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, agent_id) VALUES (?, ?, ?, ?, ?)",
                    ("entities", name, "DELETE", old_data, agent_id),
                )
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entities)} entities and recorded in audit logs."
    except Exception as e:
        log_error(f"Failed to delete entities: {entities}", e)
        return f"Error: Deletion failed: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_audit_history(content_id: str):
    """Retrieves the change history for a specific entity or bank file."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        logs = cursor.execute(
            "SELECT action, old_data, new_data, timestamp, agent_id FROM audit_logs WHERE content_id = ? ORDER BY timestamp DESC",
            (content_id,),
        ).fetchall()
        return [
            {"action": l[0], "old": l[1], "new": l[2], "at": l[3], "agent": l[4]}
            for l in logs
        ]
    finally:
        conn.close()


@mcp.tool()
def rollback_memory(audit_id: int):
    """Restores an entry to its state in a specific audit log record."""
    conn = get_connection()
    try:
        log = conn.execute(
            "SELECT table_name, content_id, old_data FROM audit_logs WHERE id = ?",
            (audit_id,),
        ).fetchone()
        if not log or not log[2]:
            return "Error: Audit record not found or has no 'old_data' to restore."

        table, cid, data_raw = log
        data = json.loads(data_raw)

        if table == "entities":
            conn.execute(
                "INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)",
                (data["name"], data["type"], data["desc"]),
            )
        elif table == "bank_files":
            conn.execute(
                "INSERT OR REPLACE INTO bank_files (filename, content, last_synced) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (cid, data["content"]),
            )

        conn.commit()
        return f"Successfully rolled back {cid} in {table}."
    except Exception as e:
        log_error(f"Rollback failed for audit_id {audit_id}", e)
        return f"Error: Rollback failed: {e}"
    finally:
        conn.close()


@mcp.tool()
async def create_snapshot(name: str, description: str = ""):
    """Creates a full snapshot (backup) of the current knowledge base."""
    import shutil
    from .utils import get_db_path

    db_path = get_db_path()
    snapshot_dir = os.path.join(os.path.dirname(db_path), "snapshots")
    if not os.path.exists(snapshot_dir):
        os.makedirs(snapshot_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = os.path.join(snapshot_dir, f"snapshot_{ts}.db")

    try:
        shutil.copy2(db_path, snapshot_file)
        conn = get_connection()
        conn.execute(
            "INSERT INTO snapshots (name, description, file_path) VALUES (?, ?, ?)",
            (name, description, snapshot_file),
        )
        conn.commit()
        conn.close()
        return f"Snapshot '{name}' created at {snapshot_file}"
    except Exception as e:
        log_error("Failed to create snapshot", e)
        return f"Error: Snapshot failed: {e}"


@mcp.tool()
async def restore_snapshot(snapshot_id: int):
    """Restores the entire knowledge base from a specific snapshot."""
    import shutil
    from .utils import get_db_path

    conn = get_connection()
    row = conn.execute(
        "SELECT file_path FROM snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    conn.close()

    if not row:
        return f"Error: Snapshot ID {snapshot_id} not found."

    snapshot_file = row[0]
    db_path = get_db_path()

    try:
        shutil.copy2(snapshot_file, db_path)
        return f"Successfully restored database from snapshot at {snapshot_file}"
    except Exception as e:
        log_error("Failed to restore snapshot", e)
        return f"Error: Restore failed: {e}"


@mcp.tool()
async def repair_memory():
    """Syncs mirrored content from SQLite back to the physical Markdown files."""
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        files = cursor.execute("SELECT filename, content FROM bank_files").fetchall()
        count = 0
        for filename, content in files:
            path = os.path.join(bank_dir, filename)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)
            count += 1
        results.append(f"Restored {count} files from DB to disk.")
    except Exception as e:
        log_error("Memory repair (DB to Disk) failed", e)
        results.append(f"Error: Repair failed: {e}")
    finally:
        conn.close()
    return " | ".join(results)


@mcp.tool()
async def archive_memory(threshold: float = 0.1):
    """
    Archives low-importance knowledge that falls below the importance threshold.
    """
    conn = get_connection()
    results = []
    try:
        cursor = conn.cursor()
        metadata = cursor.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        ).fetchall()

        to_archive = []
        for cid, count, last in metadata:
            score = calculate_importance(count, last)
            if score < threshold:
                to_archive.append(cid)

        if to_archive:
            # For simplicity in this version, we mark them as archived in the description
            for cid in to_archive:
                cursor.execute(
                    "UPDATE entities SET description = '[ARCHIVED] ' || description WHERE name = ? AND description NOT LIKE '[ARCHIVED]%'",
                    (cid,),
                )
            results.append(
                f"Archived {len(to_archive)} items with importance below {threshold}"
            )
        else:
            results.append("No items found below the importance threshold.")

        conn.commit()
    except Exception as e:
        log_error("Memory archival failed", e)
        results.append(f"Error: Archival failed: {e}")
    finally:
        conn.close()
    return " | ".join(results)


@mcp.tool()
async def get_memory_health():
    """
    Returns diagnostic information about the health and state of the knowledge base.
    """
    conn = get_connection()
    health = {}
    try:
        cursor = conn.cursor()
        health["entities_count"] = cursor.execute(
            "SELECT COUNT(*) FROM entities"
        ).fetchone()[0]
        health["relations_count"] = cursor.execute(
            "SELECT COUNT(*) FROM relations"
        ).fetchone()[0]
        health["observations_count"] = cursor.execute(
            "SELECT COUNT(*) FROM observations"
        ).fetchone()[0]
        health["bank_files_cached"] = cursor.execute(
            "SELECT COUNT(*) FROM bank_files"
        ).fetchone()[0]
        health["embeddings_count"] = cursor.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]

        # Importance distribution
        metadata = cursor.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        ).fetchall()
        if metadata:
            scores = [calculate_importance(m[1], m[2]) for m in metadata]
            health["importance_stats"] = {
                "avg": round(sum(scores) / len(scores), 2),
                "std_dev": round(float(np.std(scores)), 2),
                "max": round(max(scores), 2),
                "min": round(min(scores), 2),
            }
            health["archive_candidates_count"] = sum(1 for s in scores if s < 0.1)

        # Model distribution
        models = cursor.execute(
            "SELECT model_name, COUNT(*) FROM embeddings GROUP BY model_name"
        ).fetchall()
        health["model_distribution"] = {m[0]: m[1] for m in models}

        # Check for missing embeddings
        health["missing_embeddings"] = (
            health["entities_count"]
            + health["bank_files_cached"]
            - health["embeddings_count"]
        )

        # BYOK Check
        health["semantic_search_active"] = get_gemini_client() is not None

        # --- GAPS & BIAS DETECTION (Phase 11) ---
        # 1. Isolation Detection
        isolated = cursor.execute("""
            SELECT name FROM entities 
            WHERE name NOT IN (SELECT source FROM relations) 
            AND name NOT IN (SELECT target FROM relations)
        """).fetchall()
        health["gaps_analysis"] = {
            "isolated_entities_count": len(isolated),
            "isolated_entities": [i[0] for i in isolated[:10]],  # List first 10
        }

        # 2. Graph Density
        if health["entities_count"] > 1:
            max_relations = health["entities_count"] * (health["entities_count"] - 1)
            health["gaps_analysis"]["graph_density"] = round(
                health["relations_count"] / max_relations, 4
            )
        else:
            health["gaps_analysis"]["graph_density"] = 0

        # 3. Entity Type Distribution (Bias detection)
        type_dist = cursor.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        ).fetchall()
        health["bias_analysis"] = {t[0]: t[1] for t in type_dist}

        # Suggestion based on sparsity
        if len(type_dist) < 3:
            health["bias_analysis"]["warning"] = (
                "Low taxonomy diversity. Consider categorizing entities more granularly."
            )

        # 4. Agent Attribution Stats
        agent_stats = cursor.execute(
            "SELECT created_by, COUNT(*) FROM entities GROUP BY created_by"
        ).fetchall()
        health["agent_contribution"] = {
            a[0] if a[0] else "legacy": a[1] for a in agent_stats
        }

    except Exception as e:
        log_error("Health diagnostics failed", e)
        health["error"] = str(e)
    finally:
        conn.close()
    return health


# --- INITIALIZATION ---
def main():
    init_db()
    import asyncio

    asyncio.run(initialize_bank())
    mcp.run()


if __name__ == "__main__":
    main()
