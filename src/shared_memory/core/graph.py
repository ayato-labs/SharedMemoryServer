import asyncio
import hashlib
import json
from typing import Any

import aiosqlite
from google import genai

from shared_memory.common.utils import get_gemini_client, get_logger, log_error
from shared_memory.infra.database import async_get_connection, retry_on_db_lock

logger = get_logger("graph")


async def get_graph_data() -> dict[str, Any]:
    \"\"\"Fetches the current state of the knowledge graph.\"\"\"
    async with async_get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(\"SELECT subject, relation, object FROM graph\")
        rows = await cursor.fetchall()
        # Convert to list of dicts for frontend/API
        relations = [{\"subject\": r[0], \"relation\": r[1], \"object\": r[2]} for r in rows]
        return {\"relations\": relations}


@retry_on_db_lock()
async def save_entities(
    entities: list[dict[str, Any]],
    agent_id: str,
    conn: aiosqlite.Connection,
    precomputed_vectors: list[list[float]] | None = None,
) -> str:
    \"\"\"Saves multiple entities with their metadata and embeddings.\"\"\"
    try:
        cursor = await conn.cursor()
        saved_count = 0
        for i, entity in enumerate(entities):
            name = entity.get(\"name\")
            if not name:
                continue

            entity_type = entity.get(\"entity_type\", \"concept\")
            description = entity.get(\"description\", \"\")
            metadata = entity.get(\"metadata\", {})

            # Use precomputed vector if available
            vector = None
            if precomputed_vectors and i < len(precomputed_vectors):
                vector = precomputed_vectors[i]

            vector_json = json.dumps(vector) if vector else None
            metadata_json = json.dumps(metadata)

            await cursor.execute(
                \"\"\"
                INSERT INTO entities (name, entity_type, description, metadata, embedding, agent_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    description = excluded.description,
                    metadata = excluded.metadata,
                    embedding = COALESCE(excluded.embedding, entities.embedding),
                    updated_at = CURRENT_TIMESTAMP
                \"\"\",
                (name, entity_type, description, metadata_json, vector_json, agent_id),
            )
            saved_count += 1

            # SSoT: Update Access Metadata
            from shared_memory.infra.database import update_access

            await update_access(name, conn=conn)

        return f\"Saved {saved_count} entities\"
    except Exception as e:
        log_error(\"Error in save_entities\", e)
        raise e


@retry_on_db_lock()
async def save_relations(
    relations: list[dict[str, Any]], agent_id: str, conn: aiosqlite.Connection
) -> str:
    \"\"\"Saves multiple relations between entities.\"\"\"
    try:
        cursor = await conn.cursor()
        saved_count = 0
        for rel in relations:
            subject = rel.get(\"subject\")
            relation = rel.get(\"relation\")
            obj = rel.get(\"object\")

            if not (subject and relation and obj):
                continue

            await cursor.execute(
                \"\"\"
                INSERT INTO graph (subject, relation, object, agent_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(subject, relation, object) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                \"\"\",
                (subject, relation, obj, agent_id),
            )
            saved_count += 1
        return f\"Saved {saved_count} relations\"
    except Exception as e:
        log_error(\"Error in save_relations\", e)
        raise e


async def check_conflict(
    entity_name: str, new_contents: list[str], agent_id: str, conn: aiosqlite.Connection | None = None
) -> list[tuple[bool, str | None]]:
    \"\"\"
    Checks for semantic conflicts using Gemini 2.0.
    Returns a list of (is_conflict, reason) tuples matching the new_contents order.
    \"\"\"
    if not new_contents:
        return []

    try:
        client = get_gemini_client()
        if not client:
            log_error(\"Conflict check aborted: Gemini client not initialized (check API key)\")
            return [(False, None)] * len(new_contents)

        logger.info(f\"Checking conflicts for entity='{entity_name}' ({len(new_contents)} items)\")
        if conn is None:
            async with async_get_connection() as managed_conn:
                return await _check_conflicts_internal(
                    entity_name, new_contents, agent_id, managed_conn, client
                )
        else:
            return await _check_conflicts_internal(
                entity_name, new_contents, agent_id, conn, client
            )
    except Exception as e:
        log_error(\"Conflict check failed\", e)
        raise e


async def _check_conflicts_internal(
    entity_name: str,
    new_contents: list[str],
    agent_id: str,
    conn: aiosqlite.Connection,
    client: genai.Client,
) -> list[tuple[bool, str | None]]:
    \"\"\"Actual logic for conflict check once connection is acquired.\"\"\"
    # 1. Fetch existing observations for this entity
    cursor = await conn.cursor()
    await cursor.execute(
        \"SELECT content FROM observations WHERE entity_name = ? AND agent_id = ? LIMIT 10\",
        (entity_name, agent_id),
    )
    existing_rows = await cursor.fetchall()
    existing_knowledge = [r[0] for r in existing_rows]

    if not existing_knowledge:
        return [(False, None)] * len(new_contents)

    # 2. Use Gemini to detect conflicts
    # We ask Gemini to evaluate each new content against the existing pool
    prompt = f\"\"\"
Entity: {entity_name}
Existing Knowledge:
{chr(10).join(f'- {k}' for k in existing_knowledge)}

New Observations to check:
{chr(10).join(f'{i}: {c}' for i, c in enumerate(new_contents))}

Instructions:
Identify if any NEW observation contradicts or significantly duplicates existing knowledge.
Return a JSON array of objects with exactly {len(new_contents)} items.
Format: {{\"results\": [{{\"index\": 0, \"conflict\": true/false, \"reason\": \"...\"}}, ...]}}
Only mark 'conflict: true' for logical contradictions or identical repetitions.
\"\"\"

    try:
        response = client.models.generate_content(
            model=\"gemini-2.0-flash\",
            contents=prompt,
            config={
                \"response_mime_type\": \"application/json\",
            },
        )
        res_data = json.loads(response.text)
        results_map = {item[\"index\"]: item for item in res_data.get(\"results\", [])}

        final_results = []
        for i in range(len(new_contents)):
            r = results_map.get(i, {\"conflict\": False, \"reason\": None})
            final_results.append((r.get(\"conflict\", False), r.get(\"reason\")))
        return final_results
    except Exception as e:
        log_error(\"Gemini conflict check API failed\", e)
        return [(False, None)] * len(new_contents)


@retry_on_db_lock()
async def save_observations(
    observations: list[dict[str, Any]],
    agent_id: str,
    conn: aiosqlite.Connection,
    precomputed_conflicts: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    \"\"\"Saves multiple observations, skipping semantic conflicts.\"\"\"
    try:
        cursor = await conn.cursor()
        saved_count = 0
        conflicts_found = []

        for i, obs in enumerate(observations):
            content = obs.get(\"content\")
            entity_name = obs.get(\"entity_name\", \"Unknown\")
            if not content:
                continue

            # Check precomputed conflicts
            is_conflict = False
            reason = None
            if precomputed_conflicts and i < len(precomputed_conflicts):
                is_conflict = precomputed_conflicts[i].get(\"is_conflict\", False)
                reason = precomputed_conflicts[i].get(\"reason\")

            if is_conflict:
                conflicts_found.append({\"entity\": entity_name, \"content\": content, \"reason\": reason})
                continue

            # Content ID for deduplication (SSoT)
            content_id = hashlib.sha256(f\"{entity_name}:{content}\".encode()).hexdigest()

            await cursor.execute(
                \"\"\"
                INSERT INTO observations (content_id, entity_name, content, agent_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(content_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                \"\"\",
                (content_id, entity_name, content, agent_id),
            )
            saved_count += 1

            # Update Access Metadata
            from shared_memory.infra.database import update_access

            await update_access(content_id, conn=conn)

        return f\"Saved {saved_count} observations\", conflicts_found
    except Exception as e:
        log_error(\"Error in save_observations\", e)
        raise e


async def extract_hashtags(text: str) -> list[str]:
    \"\"\"Extracts meaningful hashtags from text using Gemini.\"\"\"
    if not text or len(text) < 5:
        return []

    client = get_gemini_client()
    if not client:
        return []

    prompt = f\"\"\"Extract 2-4 relevant technical hashtags for the following text.
Text: {text}
Format: Return as JSON array of strings, e.g. [\\\"#python\\\", \\\"#asyncio\\\"]
\"\"\"
    try:
        response = client.models.generate_content(
            model=\"gemini-2.0-flash\",
            contents=prompt,
            config={\"response_mime_type\": \"application/json\"},
        )
        tags = json.loads(response.text)
        return [t if t.startswith(\"#\") else f\"#{t}\" for t in tags if isinstance(t, str)]
    except Exception:
        return []


async def save_tags(content_id: str, content_type: str, tags: list[str], conn: aiosqlite.Connection):
    \"\"\"Saves tags to the knowledge_tags table.\"\"\"
    if not tags:
        return
    try:
        cursor = await conn.cursor()
        for tag in tags:
            await cursor.execute(
                \"\"\"
                INSERT INTO knowledge_tags (content_id, content_type, tag)
                VALUES (?, ?, ?)
                ON CONFLICT DO NOTHING
                \"\"\",
                (content_id, content_type, tag),
            )
    except Exception as e:
        log_error(\"Error saving tags\", e)
