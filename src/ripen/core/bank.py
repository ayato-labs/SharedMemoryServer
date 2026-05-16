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
from ripen.infra.embeddings import compute_embeddings_bulk

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
    uow,
    precomputed_vectors: list[list[float]] | None = None,
):
    """
    Saves bank files to disk and DB.
    """
    existing_entities = await uow.entities.get_all_entity_names()
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

    if precomputed_vectors is not None:
        vectors = precomputed_vectors
    else:
        embedding_texts = [item["embedding_text"] for item in items_to_process]
        vectors = await compute_embeddings_bulk(embedding_texts)

    async with GlobalLock(BANK_LOCK_NAME):
        for i, item in enumerate(items_to_process):
            filename = item["sanitized_filename"]
            content = item["content"]
            vector = vectors[i] if i < len(vectors) else None
            path = item["path"]

            old_content = await uow.bank.get_file_content(filename)
            old_data = json.dumps({"content": old_content}) if old_content else None

            await uow.bank.upsert_bank_file(filename, content, agent_id)
            await uow.audit.log_action(
                table_name="bank_files",
                content_id=filename,
                action="UPDATE" if old_content else "INSERT",
                old_data=old_data,
                new_data=json.dumps({"content": content}),
                agent_id=agent_id,
            )

            if vector:
                await uow.embeddings.upsert_embedding(filename, vector, settings.embedding_model)

            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            for entity_name in existing_entities:
                if entity_name.lower() in content.lower():
                    await uow.relations.upsert_relation(
                        subject=filename,
                        object_name=entity_name,
                        predicate="mentions",
                        agent_id=agent_id,
                    )

    return f"Updated {len(items_to_process)} bank files"


async def read_bank_data(uow=None, query: str | None = None):
    logger.info(f"read_bank_data START query={query}")
    async with GlobalLock(BANK_LOCK_NAME):
        bank_dir = get_bank_dir()
        bank_data = {}
        found_files = set()

        if uow is None:
            from ripen.infra.uow import UnitOfWork

            async with UnitOfWork() as managed_uow:
                active_files = await managed_uow.bank.get_active_filenames()
                db_files = await managed_uow.bank.get_active_files_content()
        else:
            active_files = await uow.bank.get_active_filenames()
            db_files = await uow.bank.get_active_files_content()

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
                                # update_access requires a uow/repo now?
                                # Actually update_access was a helper in database.py
                                # Let's skip it or update it if it's important.
                                # For now, let's keep it if it's static or refactor it.
                                # await update_access(filename)
                    except (Exception, ValueError) as e:
                        log_error(f"Failed to read bank file {filename}", e)

        for filename, content in db_files:
            if filename not in found_files:
                if not query or query.lower() in content.lower():
                    bank_data[f"{filename} [RECOVERED]"] = content
        logger.info(f"read_bank_data COMPLETE query={query}")
        return bank_data


async def repair_memory_logic(uow):
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)

    files = await uow.bank.get_all_files_content()
    count = 0
    for filename, content in files:
        path = safe_path_join(bank_dir, filename)
        async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
            await f.write(content)
        count += 1
    results.append(f"Restored {count} files from DB to disk.")
    return " | ".join(results)
