import json
import os

import aiofiles

from shared_memory.database import get_connection, update_access
from shared_memory.embeddings import EMBEDDING_MODEL, compute_embeddings_bulk
from shared_memory.utils import (
    GlobalLock,
    get_bank_dir,
    log_error,
    mask_sensitive_data,
    safe_path_join,
)

BANK_FILES = {
    "projectBrief.md": "Core requirements and goals.",
    "productContext.md": "Why this project exists and its scope.",
    "activeContext.md": "What we are working on now and recent decisions.",
    "systemPatterns.md": "Architecture, design patterns, and technical decisions.",
    "techContext.md": "Tech stack, dependencies, and constraints.",
    "progress.md": "Status, roadmap, and what's next.",
    "decisionLog.md": "Record of significant technical choices.",
}

# Global lock name for cross-process synchronization
BANK_LOCK_NAME = "shared_memory_bank"


async def initialize_bank():
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    for filename, description in BANK_FILES.items():
        try:
            path = safe_path_join(bank_dir, filename)
            if not os.path.exists(path):
                async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                    await f.write(
                        f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n"
                    )
        except ValueError as e:
            log_error(f"Initialization skipped for invalid filename: {filename}", e)


async def save_bank_files(bank_files: dict[str, str], agent_id: str, conn):
    async with GlobalLock(BANK_LOCK_NAME):
        existing_entities = [
            r[0] for r in conn.execute("SELECT name FROM entities").fetchall()
        ]
        bank_dir = get_bank_dir()
        # 1. Pre-process and collect texts for bulk embedding
        items_to_process = []
        for filename, content in bank_files.items():
            try:
                path = safe_path_join(bank_dir, filename)
                sanitized_filename = os.path.basename(path)
                masked_content = mask_sensitive_data(content)
                items_to_process.append(
                    {
                        "original_filename": filename,
                        "sanitized_filename": sanitized_filename,
                        "path": path,
                        "content": masked_content,
                        "embedding_text": f"File: {sanitized_filename}\nContent: {masked_content}",
                    }
                )
            except ValueError as e:
                log_error(f"Skipping file due to safety violation: {filename}", e)

        if not items_to_process:
            return "Updated 0 bank files"

        # 2. Bulk Compute Embeddings
        embedding_texts = [item["embedding_text"] for item in items_to_process]
        vectors = await compute_embeddings_bulk(embedding_texts)

        # 3. Synchronize DB and Disk
        for i, item in enumerate(items_to_process):
            filename = item["sanitized_filename"]
            content = item["content"]
            vector = vectors[i]
            path = item["path"]

            # DB Sync
            old_content = conn.execute(
                "SELECT content FROM bank_files WHERE filename = ?", (filename,)
            ).fetchone()
            old_data = json.dumps({"content": old_content[0]}) if old_content else None

            conn.execute(
                "INSERT OR REPLACE INTO bank_files (filename, content, updated_by) VALUES (?, ?, ?)",
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

            # Vector Sync
            if vector:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                    (filename, json.dumps(vector).encode("utf-8"), EMBEDDING_MODEL),
                )

            # Disk Sync
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            # Mentions Detection
            for entity_name in existing_entities:
                if entity_name.lower() in content.lower():
                    conn.execute(
                        "INSERT OR REPLACE INTO relations (source, target, relation_type, created_by) VALUES (?, ?, ?, ?)",
                        (filename, entity_name, "mentions", agent_id),
                    )

        return f"Updated {len(items_to_process)} bank files"


async def read_bank_data(query: str | None = None):
    async with GlobalLock(BANK_LOCK_NAME):
        bank_dir = get_bank_dir()
        bank_data = {}
        found_files = set()

        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".md"):
                    try:
                        path = safe_path_join(bank_dir, filename)
                        async with aiofiles.open(path, encoding="utf-8") as f:
                            content = await f.read()
                            if not query or query.lower() in content.lower():
                                bank_data[filename] = content
                                found_files.add(filename)
                                await update_access(filename)
                    except (Exception, ValueError) as e:
                        log_error(f"Failed to read bank file {filename}", e)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        db_files = cursor.execute("SELECT filename, content FROM bank_files").fetchall()
        for filename, content in db_files:
            if filename not in found_files:
                if not query or query.lower() in content.lower():
                    bank_data[f"{filename} [RECOVERED]"] = content
    finally:
        conn.close()
    return bank_data


async def repair_memory_logic():
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
    finally:
        conn.close()
    return " | ".join(results)
