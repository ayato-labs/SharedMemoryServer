import json
import os

import aiofiles

from ripen.common.config import settings
from ripen.common.utils import (
    GlobalLock,
    get_bank_dir,
    get_logger,
    log_error,
    mask_sensitive_data,
    safe_path_join,
)
from ripen.infra.database import async_get_connection, update_access
from ripen.infra.embeddings import compute_embeddings_bulk
from ripen.infra.repository import (
    AuditRepository,
    BankRepository,
    EmbeddingRepository,
    EntityRepository,
    RelationRepository,
)

logger = get_logger("bank")

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
                    await f.write(f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n")
        except ValueError as e:
            log_error(f"Initialization skipped for invalid filename: {filename}", e)


async def save_bank_files(
    bank_files: dict[str, str],
    agent_id: str,
    conn,
    precomputed_vectors: list[list[float]] | None = None,
):
    """
    Saves bank files to disk and DB.
    Optimized to wrap file operations in a single lock session.
    """
    existing_entities = await EntityRepository.get_all_entity_names(conn)
    bank_dir = get_bank_dir()
    os.makedirs(bank_dir, exist_ok=True)

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
                    "embedding_text": (f"File: {sanitized_filename}\nContent: {masked_content}"),
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
            old_content = await BankRepository.get_file_content(conn, filename)
            old_data = json.dumps({"content": old_content}) if old_content else None

            await BankRepository.upsert_bank_file(conn, filename, content, agent_id)
            await AuditRepository.log_action(
                conn=conn,
                table_name="bank_files",
                content_id=filename,
                action="UPDATE" if old_content else "INSERT",
                old_data=old_data,
                new_data=json.dumps({"content": content}),
                agent_id=agent_id,
            )

            # 2. Vector Sync
            if vector:
                await EmbeddingRepository.upsert_embedding(conn, filename, vector, settings.embedding_model)

            # 3. Disk Sync
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            # 4. Mentions Detection
            for entity_name in existing_entities:
                if entity_name.lower() in content.lower():
                    await RelationRepository.upsert_relation(
                        conn, subject=filename, object_name=entity_name, predicate="mentions", agent_id=agent_id
                    )

    return f"Updated {len(items_to_process)} bank files"


async def read_bank_data(query: str | None = None):
    # Lock for disk read to ensure atomicity
    logger.info(f"read_bank_data START query={query}")
    async with GlobalLock(BANK_LOCK_NAME):
        logger.debug(f"GlobalLock ACQUIRED query={query}")
        bank_dir = get_bank_dir()
        bank_data = {}
        found_files = set()

        # Step 1: Get list of ACTIVE files from DB
        active_files = await BankRepository.get_active_filenames()

        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".md") and filename in active_files:
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

        # Step 2: Merge with recovering data from DB (only active ones)
        db_files = await BankRepository.get_active_files_content()
        for filename, content in db_files:
            if filename not in found_files:
                if not query or query.lower() in content.lower():
                    # Mark as recovered to avoid confusion
                    bank_data[f"{filename} [RECOVERED]"] = content
        logger.info(f"read_bank_data COMPLETE query={query}")
        return bank_data


async def repair_memory_logic():
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)

    async with await async_get_connection() as conn:
        files = await BankRepository.get_all_files_content(conn)
        count = 0
        for filename, content in files:
            path = safe_path_join(bank_dir, filename)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)
            count += 1
        results.append(f"Restored {count} files from DB to disk.")
    return " | ".join(results)
