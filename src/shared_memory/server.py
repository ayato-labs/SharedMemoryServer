import os
import sqlite3
import aiofiles
import pickle
import numpy as np
import math
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP

from .utils import log_error, get_bank_dir
from .database import get_connection, init_db, update_access
from .logic import cosine_similarity, batch_cosine_similarity, calculate_importance
from .embeddings import get_gemini_client, compute_embedding, EMBEDDING_MODEL

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
):
    """
    Unified write tool for both Knowledge Graph and Memory Bank.
    - entities: List of {name, entity_type, description}
    - relations: List of {source, target, relation_type}
    - observations: List of {entity_name, content}
    - bank_files: Dict of {filename: content}
    """
    results = []
    conn = get_connection()
    try:
        if entities:
            for e in entities:
                conn.execute(
                    "INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)",
                    (e["name"], e["entity_type"], e.get("description", "")),
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
            for r in relations:
                conn.execute(
                    "INSERT OR REPLACE INTO relations (source, target, relation_type) VALUES (?, ?, ?)",
                    (r["source"], r["target"], r["relation_type"]),
                )
            results.append(f"Saved {len(relations)} relations")

        if observations:
            for o in observations:
                conn.execute(
                    "INSERT INTO observations (entity_name, content) VALUES (?, ?)",
                    (o["entity_name"], o["content"]),
                )
            results.append(f"Saved {len(observations)} observations")

            # Implicit Mention Detection
            existing_entities = [
                row[0] for row in conn.execute("SELECT name FROM entities").fetchall()
            ]
            for filename, content in bank_files.items() if bank_files else []:
                if not filename.endswith(".md"):
                    filename += ".md"
                conn.execute(
                    "INSERT OR REPLACE INTO bank_files (filename, content, last_synced) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (filename, content),
                )

                # Scan for mentions
                for entity_name in existing_entities:
                    if entity_name.lower() in content.lower():
                        conn.execute(
                            "INSERT OR REPLACE INTO relations (source, target, relation_type) VALUES (?, ?, ?)",
                            (filename, entity_name, "mentions"),
                        )

                # Semantic segment
                vector = await compute_embedding(f"File: {filename}\nContent:\n{content}")
                if vector:
                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                        (filename, pickle.dumps(vector), EMBEDDING_MODEL),
                    )
            if bank_files:
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
            try:
                async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                    await f.write(content)
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
                e_cols = [col[0] for col in cursor.description]
                e_rows = e_matches.fetchall()
                
                o_matches = cursor.execute(
                    "SELECT * FROM observations WHERE content LIKE ?", (q,)
                ).fetchall()
                for row in e_rows:
                    update_access(row[0])
                response["graph"] = {
                    "entities": [
                        {"name": r[0], "type": r[1], "description": r[2]} for r in e_rows
                    ],
                    "observations": [
                        {"entity": o[1], "content": o[2], "at": o[3]} for o in o_matches
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
                        {"source": r[0], "target": r[1], "type": r[2]}
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

                    # Get importance scores
                    metadata = cursor.execute(
                        "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
                    ).fetchall()
                    importance_map = {
                        m[0]: calculate_importance(m[1], m[2]) for m in metadata
                    }

                    # Hybrid ranking: Similarity * Importance
                    hybrid_results = []
                    for cid, score in semantic_results:
                        imp_weight = importance_map.get(cid, 1.0)
                        final_score = score * (0.8 + 0.2 * math.log1p(imp_weight))
                        hybrid_results.append((cid, final_score, score, imp_weight))

                    hybrid_results.sort(key=lambda x: x[1], reverse=True)
                    response["semantic_hits"] = [
                        {
                            "id": r[0],
                            "score": round(float(r[1]), 4),
                            "base_similarity": round(float(r[2]), 4),
                            "importance": round(r[3], 2),
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
def delete_memory(entities: List[str]):
    """Removes specific entities and their associated data from the Knowledge Graph."""
    conn = get_connection()
    try:
        for name in entities:
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entities)} entities and all related observations/relations."
    except Exception as e:
        log_error(f"Failed to delete entities: {entities}", e)
        return f"Error: Deletion failed: {e}"
    finally:
        conn.close()

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
