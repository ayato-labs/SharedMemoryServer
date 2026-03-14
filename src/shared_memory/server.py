from fastmcp import FastMCP
import sqlite3
import os
import aiofiles
import json
from typing import List, Optional, Dict, Any
import numpy as np
import pickle
from google import genai

mcp = FastMCP("SharedMemoryServer")

# --- CONFIGURATION HELPERS ---
def get_db_path():
    return os.environ.get("MEMORY_DB_PATH", "shared_memory.db")

def get_bank_dir():
    return os.environ.get("MEMORY_BANK_DIR", "memory-bank")

def init_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            entity_type TEXT,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            source TEXT,
            target TEXT,
            relation_type TEXT,
            PRIMARY KEY (source, target, relation_type),
            FOREIGN KEY (source) REFERENCES entities (name) ON DELETE CASCADE,
            FOREIGN KEY (target) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_name) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_files (
            filename TEXT PRIMARY KEY,
            content TEXT,
            last_synced DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            content_id TEXT PRIMARY KEY,
            vector BLOB,
            model_name TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_metadata (
            content_id TEXT PRIMARY KEY,
            access_count INTEGER DEFAULT 0,
            last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
            importance_score REAL DEFAULT 1.0
        )
    """)
    conn.commit()
    conn.close()

# --- EMBEDDING HELPERS (BYOK Fallback) ---
EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONALITY = 768

def get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except:
        return None

async def compute_embedding(text: str):
    client = get_gemini_client()
    if not client:
        return None
    try:
        # We use sync client in async wrapper for simplicity if needed, 
        # but google-genai client is generally blocking. 
        # FastMCP runs things in threads if not async? 
        # Actually google-genai client is blocking.
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": DIMENSIONALITY}
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"[EMBEDDING ERROR] {e}")
        return None

def cosine_similarity(v1, v2):
    if v1 is None or v2 is None: return 0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def calculate_importance(access_count, last_accessed_str):
    from datetime import datetime
    import math
    try:
        last_accessed = datetime.strptime(last_accessed_str, "%Y-%m-%d %H:%M:%S")
    except:
        last_accessed = datetime.now()
    
    # Decay Factor (lambda = 0.0001 per minute ~ roughly half in 5 days)
    delta_minutes = (datetime.now() - last_accessed).total_seconds() / 60
    decay = math.exp(-0.0001 * delta_minutes)
    return (access_count + 1) * decay

def update_access(content_id: str):
    conn = sqlite3.connect(get_db_path())
    try:
        conn.execute("""
            INSERT INTO knowledge_metadata (content_id, access_count, last_accessed, importance_score)
            VALUES (?, 1, CURRENT_TIMESTAMP, 1.0)
            ON CONFLICT(content_id) DO UPDATE SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
        """, (content_id,))
        conn.commit()
    except: pass
    finally: conn.close()

# --- MEMORY BANK STORAGE (Markdown) ---
BANK_FILES = {
    "projectBrief.md": "Core requirements and goals.",
    "productContext.md": "Why this project exists and its scope.",
    "activeContext.md": "What we are working on now and recent decisions.",
    "systemPatterns.md": "Architecture, design patterns, and technical decisions.",
    "techContext.md": "Tech stack, dependencies, and constraints.",
    "progress.md": "Status, roadmap, and what's next.",
    "decisionLog.md": "Record of significant technical choices."
}

async def initialize_bank():
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    for filename, description in BANK_FILES.items():
        path = os.path.join(bank_dir, filename)
        if not os.path.exists(path):
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n")

# --- GRAPH TOOLS (Official MCP Logic) ---

# --- UNIFIED TOOLS (V2 API) ---

@mcp.tool()
async def save_memory(
    entities: Optional[List[Dict[str, str]]] = None,
    relations: Optional[List[Dict[str, str]]] = None,
    observations: Optional[List[Dict[str, str]]] = None,
    bank_files: Optional[Dict[str, str]] = None
):
    """
    Unified write tool for both Knowledge Graph and Memory Bank.
    - entities: List of {name, entity_type, description}
    - relations: List of {source, target, relation_type}
    - observations: List of {entity_name, content}
    - bank_files: Dict of {filename: content}
    """
    results = []
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if entities:
            for e in entities:
                conn.execute("INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)", 
                             (e['name'], e['entity_type'], e.get('description', '')))
                # Semantic segment
                vector = await compute_embedding(f"{e['name']} ({e['entity_type']}): {e.get('description', '')}")
                if vector:
                    conn.execute("INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                                 (e['name'], pickle.dumps(vector), EMBEDDING_MODEL))
            results.append(f"Saved {len(entities)} entities (with embeddings)")
        
        if relations:
            for r in relations:
                conn.execute("INSERT OR REPLACE INTO relations (source, target, relation_type) VALUES (?, ?, ?)", 
                             (r['source'], r['target'], r['relation_type']))
            results.append(f"Saved {len(relations)} relations")
            
        if observations:
            for o in observations:
                conn.execute("INSERT INTO observations (entity_name, content) VALUES (?, ?)", 
                             (o['entity_name'], o['content']))
                # Observations contribute to entity context but for now we embed per entity
            results.append(f"Saved {len(observations)} observations")
        
        if bank_files:
            for filename, content in bank_files.items():
                if not filename.endswith(".md"):
                    filename += ".md"
                conn.execute("INSERT OR REPLACE INTO bank_files (filename, content, last_synced) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                             (filename, content))
                # Semantic segment
                vector = await compute_embedding(f"File: {filename}\nContent:\n{content}")
                if vector:
                    conn.execute("INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                                 (filename, pickle.dumps(vector), EMBEDDING_MODEL))
            results.append(f"Mirrored {len(bank_files)} bank files in DB (with embeddings)")

        conn.commit()
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
                async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                    await f.write(content)
                file_count += 1
            except Exception as e:
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
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            if query:
                q = f"%{query}%"
                e_matches = cursor.execute("SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?", (q, q)).fetchall()
                o_matches = cursor.execute("SELECT * FROM observations WHERE content LIKE ?", (q,)).fetchall()
                for e in e_matches:
                    update_access(e[0])
                response["graph"] = {
                    "entities": [{"name": e[0], "type": e[1], "description": e[2]} for e in e_matches],
                    "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in o_matches]
                }
            else:
                entities = cursor.execute("SELECT * FROM entities").fetchall()
                relations = cursor.execute("SELECT * FROM relations").fetchall()
                obs = cursor.execute("SELECT * FROM observations").fetchall()
                response["graph"] = {
                    "entities": [{"name": e[0], "type": e[1], "description": e[2]} for e in entities],
                    "relations": [{"source": r[0], "target": r[1], "type": r[2]} for r in relations],
                    "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in obs]
                }
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
                        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                            content = await f.read()
                            if not query or query.lower() in content.lower():
                                bank_data[filename] = content
                                found_files.add(filename)
                                update_access(filename)
                    except: pass

        # Fallback/Supplemental: Read from DB mirror
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            db_files = cursor.execute("SELECT filename, content FROM bank_files").fetchall()
            for filename, content in db_files:
                if filename not in found_files:
                    if not query or query.lower() in content.lower():
                        bank_data[f"{filename} [RECOVERED]"] = content
        finally:
            conn.close()
        
        response["bank"] = bank_data

    # 3. SEMANTIC SEARCH (Hybrid Reranking)
    if query and get_gemini_client():
        query_vector = await compute_embedding(query)
        if query_vector:
            conn = sqlite3.connect(get_db_path())
            try:
                cursor = conn.cursor()
                all_embeddings = cursor.execute("SELECT content_id, vector, model_name FROM embeddings").fetchall()
                semantic_results = []
                for cid, v_blob, model in all_embeddings:
                    vector = pickle.loads(v_blob)
                    score = cosine_similarity(query_vector, vector)
                    semantic_results.append((cid, score, model))
                
                # Get importance scores
                metadata = cursor.execute("SELECT content_id, access_count, last_accessed FROM knowledge_metadata").fetchall()
                importance_map = {m[0]: calculate_importance(m[1], m[2]) for m in metadata}

                # Hybrid ranking: Similarity * Importance
                hybrid_results = []
                for cid, score, model in semantic_results:
                    imp_weight = importance_map.get(cid, 1.0)
                    final_score = score * (0.8 + 0.2 * math.log1p(imp_weight)) # Subtle boost
                    hybrid_results.append((cid, final_score, score, imp_weight))
                
                hybrid_results.sort(key=lambda x: x[1], reverse=True)
                response["semantic_hits"] = [
                    {"id": r[0], "score": round(r[1], 4), "base_similarity": round(r[2], 4), "importance": round(r[3], 2)} 
                    for r in hybrid_results[:5] if r[2] > 0.3
                ]
            finally:
                conn.close()

    return response

@mcp.tool()
def delete_memory(entities: List[str]):
    """Removes specific entities and their associated data from the Knowledge Graph."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for name in entities:
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entities)} entities and all related observations/relations."
    finally:
        conn.close()

@mcp.tool()
async def repair_memory():
    """Syncs mirrored content from SQLite back to the physical Markdown files."""
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    
    conn = sqlite3.connect(get_db_path())
    try:
        cursor = conn.cursor()
        files = cursor.execute("SELECT filename, content FROM bank_files").fetchall()
        count = 0
        for filename, content in files:
            path = os.path.join(bank_dir, filename)
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(content)
            count += 1
        results.append(f"Restored {count} files from DB to disk.")
    finally:
        conn.close()
    return " | ".join(results)

@mcp.tool()
async def archive_memory(threshold: float = 0.1):
    """
    Archives low-importance knowledge that falls below the importance threshold.
    """
    conn = sqlite3.connect(get_db_path())
    results = []
    try:
        cursor = conn.cursor()
        metadata = cursor.execute("SELECT content_id, access_count, last_accessed FROM knowledge_metadata").fetchall()
        
        to_archive = []
        for cid, count, last in metadata:
            score = calculate_importance(count, last)
            if score < threshold:
                to_archive.append(cid)
        
        if to_archive:
            # For simplicity in this version, we mark them as archived in the description
            # or move them to a different category.
            for cid in to_archive:
                cursor.execute("UPDATE entities SET description = '[ARCHIVED] ' || description WHERE name = ? AND description NOT LIKE '[ARCHIVED]%'", (cid,))
            results.append(f"Archived {len(to_archive)} items with importance below {threshold}")
        else:
            results.append("No items found below the importance threshold.")
        
        conn.commit()
    finally:
        conn.close()
    return " | ".join(results)

# --- INITIALIZATION ---
def main():
    init_db()
    import asyncio
    asyncio.run(initialize_bank())
    mcp.run()

if __name__ == "__main__":
    main()
