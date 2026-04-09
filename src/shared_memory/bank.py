import json
import os

import aiofiles

from shared_memory.database import async_get_connection, update_access
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


async def save_bank_files(
    bank_files: dict[str, str],
    agent_id: str,
    conn,
    precomputed_vectors: list[list[float]] | None = None
):
    """
    Saves bank files to disk and DB.
    Optimized to wrap file operations in a single lock session.
    """
    cursor = await conn.execute("SELECT name FROM entities")
    existing_entities = [r[0] for r in await cursor.fetchall()]
    bank_dir = get_bank_dir()

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
                    "embedding_text": (
                        f"File: {sanitized_filename}\n"
                        f"Content: {masked_content}"
                    ),
                }
            )
        except ValueError as e:
            log_error(f"Skipping file due to safety violation: {filename}", e)

    if not items_to_process:
        return "Updated 0 bank files"

    # Get Vectors
    if precomputed_vectors is not None:
        vectors = precomputed_vectors
    else:
        embedding_texts = [item["embedding_text"] for item in items_to_process]
        vectors = await compute_embeddings_bulk(embedding_texts)

    # Acquire bank lock once for all file operations
    async with GlobalLock(BANK_LOCK_NAME):
        for i, item in enumerate(items_to_process):
            filename = item["sanitized_filename"]
            content = item["content"]
            vector = vectors[i] if i < len(vectors) else None
            path = item["path"]

            # 1. DB Sync
            # Using same connection but explicit fetch
            cursor = await conn.execute(
                "SELECT content FROM bank_files WHERE filename = ?", (filename,)
            )
            old_content_row = await cursor.fetchone()
            old_data = (
                json.dumps({"content": old_content_row[0]})
                if old_content_row
                else None
            )

            await conn.execute(
                "INSERT OR REPLACE INTO bank_files "
                "(filename, content, updated_by) VALUES (?, ?, ?)",
                (filename, content, agent_id),
            )
            await conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, "
                "old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "bank_files",
                    filename,
                    "UPDATE" if old_content_row else "INSERT",
                    old_data,
                    json.dumps({"content": content}),
                    agent_id,
                ),
            )

            # 2. Vector Sync
            if vector:
                await conn.execute(
                    "INSERT OR REPLACE INTO embeddings "
                    "(content_id, vector, model_name) VALUES (?, ?, ?)",
                    (filename, json.dumps(vector).encode("utf-8"), EMBEDDING_MODEL),
                )

            # 3. Disk Sync
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            # 4. Mentions Detection
            for entity_name in existing_entities:
                if entity_name.lower() in content.lower():
                    await conn.execute(
                        "INSERT OR REPLACE INTO relations "
                        "(subject, object, predicate, created_by) "
                        "VALUES (?, ?, ?, ?)",
                        (filename, entity_name, "mentions", agent_id),
                    )

    return f"Updated {len(items_to_process)} bank files"


async def read_bank_data(query: str | None = None):
    # Lock for disk read to ensure atomicity
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
                                # update_access expects its own connection or nothing
                                await update_access(filename)
                    except (Exception, ValueError) as e:
                        log_error(f"Failed to read bank file {filename}", e)

        # Merge with recovering data from DB
        async with await async_get_connection() as conn:
            cursor = await conn.execute("SELECT filename, content FROM bank_files")
            db_files = await cursor.fetchall()
            for filename, content in db_files:
                if filename not in found_files:
                    if not query or query.lower() in content.lower():
                        # Mark as recovered to avoid confusion
                        bank_data[f"{filename} [RECOVERED]"] = content
        return bank_data


async def repair_memory_logic():
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)

    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT filename, content FROM bank_files")
        files = await cursor.fetchall()
        count = 0
        for filename, content in files:
            path = safe_path_join(bank_dir, filename)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)
            count += 1
        results.append(f"Restored {count} files from DB to disk.")
    return " | ".join(results)
