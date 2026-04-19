import json
from datetime import datetime
from typing import Any

from shared_memory.database import async_get_connection
from shared_memory.embeddings import (
    EMBEDDING_MODEL,
    compute_embeddings_bulk,
    get_gemini_client,
)
from shared_memory.utils import log_error, mask_sensitive_data


async def check_conflict(entity_name: str, new_content: str, agent_id: str, conn=None):
    """
    Checks if a new observation contradicts existing knowledge using Gemini.
    """
    try:
        client = get_gemini_client()
        if not client:
            log_error("Conflict check aborted: Gemini client not initialized (check API key)")
            return False, None

        if conn is None:
            async with await async_get_connection() as managed_conn:
                return await _check_conflict_internal(
                    entity_name, new_content, agent_id, managed_conn, client
                )
        else:
            return await _check_conflict_internal(entity_name, new_content, agent_id, conn, client)
    except Exception as e:
        log_error("Conflict check failed", e)
        return False, None


async def _check_conflict_internal(entity_name: str, new_content: str, agent_id: str, conn, client):
    # Fetch up to 3 most recent observations for context
    cursor = await conn.execute(
        "SELECT content FROM observations WHERE entity_name = ? ORDER BY timestamp DESC LIMIT 3",
        (entity_name,),
    )
    existing = await cursor.fetchall()

    if not existing:
        return False, None

    existing_text = "\n".join([f"- {row[0]}" for row in existing])
    prompt = (
        "You are a Fact-Checking Engine. Check if the following NEW statement "
        f"contradicts the EXISTING knowledge about '{entity_name}'.\n\n"
        f"EXISTING KNOWLEDGE:\n{existing_text}\n\n"
        f"NEW STATEMENT:\n{new_content}\n\n"
        'Output MUST be JSON: {"conflict": bool, "reason": "string"}'
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    data = json.loads(response.text)
    if data.get("conflict"):
        # Log to DB
        await conn.execute(
            "INSERT INTO conflicts "
            "(entity_name, existing_content, new_content, reason, agent_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_name, existing_text, new_content, data.get("reason"), agent_id),
        )
        await conn.commit()
        return True, data.get("reason")

    return False, None


async def save_entities(
    entities: list[dict[str, Any]],
    agent_id: str,
    conn,
    precomputed_vectors: list[list[float]] | None = None,
):
    """
    Saves entities to the database.
    Accepts precomputed_vectors to support 'Compute-then-Write' architecture.
    """
    results = []
    success_count = 0

    # 1. Prepare data
    items_to_process = []
    for e in entities:
        name = e.get("name", "").strip()
        if not name:
            results.append("Error: Entity name is required")
            continue

        e_type = e.get("entity_type", "concept")
        desc = e.get("description", "")
        importance = e.get("importance", 5)

        try:
            importance = max(1, min(10, int(importance)))
        except (ValueError, TypeError):
            from shared_memory.utils import get_logger

            get_logger("graph").debug(
                f"Invalid importance value for {name}: {importance}. Defaulting to 5."
            )
            importance = 5

        items_to_process.append(
            {
                "name": name,
                "type": e_type,
                "desc": desc,
                "importance": importance,
                "embedding_text": f"{name} ({e_type}): {desc}",
            }
        )

    if not items_to_process:
        if results:
            return f"Saved 0 entities (Errors: {len(results)})"
        return "Saved 0 entities"

    # 2. Assign Vectors (Precomputed or Fresh)
    if precomputed_vectors is not None:
        vectors = precomputed_vectors
    else:
        embedding_texts = [item["embedding_text"] for item in items_to_process]
        vectors = await compute_embeddings_bulk(embedding_texts)

    # 3. Fast Database Sync
    for i, item in enumerate(items_to_process):
        name = item["name"]
        e_type = item["type"]
        desc = item["desc"]
        importance = item["importance"]
        vector = vectors[i] if i < len(vectors) else None

        # Fetch old state for audit
        cursor = await conn.execute(
            "SELECT entity_type, description FROM entities WHERE name = ?", (name,)
        )
        old_row = await cursor.fetchone()
        old_data = json.dumps(dict(old_row)) if old_row else None
        action = "UPDATE" if old_row else "INSERT"

        await conn.execute(
            "INSERT OR REPLACE INTO entities "
            "(name, entity_type, description, importance, updated_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, e_type, desc, importance, agent_id),
        )

        # Log Audit
        new_data = json.dumps({"name": name, "type": e_type, "desc": desc})
        meta = json.dumps(
            {
                "model": EMBEDDING_MODEL if vector else None,
                "has_vector": bool(vector),
                "conflict_info": None,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await conn.execute(
            "INSERT INTO audit_logs (table_name, content_id, action, "
            "old_data, new_data, agent_id, meta_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("entities", name, action, old_data, new_data, agent_id, meta),
        )

        if vector:
            await conn.execute(
                "INSERT OR REPLACE INTO embeddings "
                "(content_id, vector, model_name) VALUES (?, ?, ?)",
                (name, json.dumps(vector).encode("utf-8"), EMBEDDING_MODEL),
            )
        success_count += 1

    msg = f"Saved {success_count} entities"
    if results:
        msg += f" (Errors: {len(results)})"
    return msg


async def save_relations(relations: list[dict[str, Any]], agent_id: str, conn):
    valid_relations = []
    errors = []
    for r in relations:
        # Standard terminology: Subject-Predicate-Object
        # Fallback to source/target/relation_type for migration period
        subject = (r.get("subject") or r.get("source") or "").strip()
        obj = (r.get("object") or r.get("target") or "").strip()
        predicate = (r.get("predicate") or r.get("relation_type") or "").strip()

        if not all([subject, obj, predicate]):
            msg = f"Error: Relation requires subject, object, and predicate: {r}"
            errors.append(msg)
            continue
        valid_relations.append((subject, obj, predicate, agent_id))

    if valid_relations:
        # DB schema was updated to use subject, object, predicate
        await conn.executemany(
            "INSERT OR REPLACE INTO relations "
            "(subject, object, predicate, created_by) VALUES (?, ?, ?, ?)",
            valid_relations,
        )

        # Log Audit for each relation
        for subject, obj, predicate, creator in valid_relations:
            await conn.execute(
                "INSERT INTO audit_logs (table_name, content_id, action, "
                "new_data, agent_id, meta_data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "relations",
                    f"{subject}->{predicate}->{obj}",
                    "INSERT",
                    json.dumps({"subject": subject, "object": obj, "predicate": predicate}),
                    creator,
                    json.dumps(
                        {
                            "agent_context": "relation_mapping",
                            "conflict_info": None,
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                ),
            )

    msg = f"Saved {len(valid_relations)} relations"
    if errors:
        msg += f" (Errors: {len(errors)})"
    return msg


async def save_observations(
    observations: list[dict[str, Any]],
    agent_id: str,
    conn,
    precomputed_conflicts: list[dict[str, Any]] | None = None,
):
    """
    Saves observations.
    Accepts precomputed_conflicts to minimize transaction duration.
    """
    conflicts_to_report = []
    errors = []
    success_count = 0

    for i, o in enumerate(observations):
        entity_name = o.get("entity_name", "").strip()
        content = o.get("content", "").strip()

        if not entity_name or not content:
            errors.append(f"Error: Observation requires entity_name and content: {o}")
            continue

        content = mask_sensitive_data(content)

        # Conflict check
        if precomputed_conflicts is not None:
            # Match conflict from precomputed results if available
            conflict_info = next((c for c in precomputed_conflicts if c["index"] == i), None)
            if conflict_info and conflict_info.get("is_conflict"):
                conflicts_to_report.append(
                    {"entity": entity_name, "reason": conflict_info.get("reason")}
                )
        else:
            is_conflict, reason = await check_conflict(entity_name, content, agent_id, conn=conn)
            if is_conflict:
                conflicts_to_report.append({"entity": entity_name, "reason": reason})

        await conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            (entity_name, content, agent_id),
        )
        await conn.execute(
            "UPDATE entities SET importance = MIN(importance + 1, 10), "
            "updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (entity_name,),
        )
        # Log Audit
        conflict_meta = next((c for c in conflicts_to_report if c["entity"] == entity_name), None)
        meta = json.dumps(
            {
                "agent_context": "development_trace",
                "conflict_info": conflict_meta,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await conn.execute(
            "INSERT INTO audit_logs (table_name, content_id, action, "
            "new_data, agent_id, meta_data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "observations",
                entity_name,
                "INSERT",
                json.dumps({"content": content}),
                agent_id,
                meta,
            ),
        )
        success_count += 1

    msg = f"Saved {success_count} observations"
    if errors:
        msg += f" (Errors: {len(errors)})"
    return msg, conflicts_to_report


async def get_graph_data(query: str | None = None):
    async with await async_get_connection() as conn:
        if query:
            cursor = await conn.execute(
                "SELECT * FROM entities WHERE "
                "(name LIKE ? OR description LIKE ?) AND status = 'active'",
                (f"%{query}%", f"%{query}%"),
            )
            matched_entities = await cursor.fetchall()
            matched_names = [e["name"] for e in matched_entities]

            if not matched_names:
                return {"entities": [], "relations": [], "observations": []}

            placeholders = ",".join(["?"] * len(matched_names))
            cursor = await conn.execute(
                f"SELECT * FROM relations WHERE (subject IN ({placeholders}) "
                f"OR object IN ({placeholders})) AND status = 'active'",
                matched_names + matched_names,
            )
            relations = await cursor.fetchall()

            cursor = await conn.execute(
                "SELECT * FROM observations WHERE entity_name IN "
                f"({placeholders}) AND status = 'active'",
                matched_names,
            )
            observations = await cursor.fetchall()

            return {
                "entities": [dict(e) for e in matched_entities],
                "relations": [dict(r) for r in relations],
                "observations": [
                    {
                        "entity": o["entity_name"],
                        "content": o["content"],
                        "at": o["timestamp"],
                    }
                    for o in observations
                ],
            }
        else:
            cursor = await conn.execute("SELECT * FROM entities WHERE status = 'active'")
            entities = await cursor.fetchall()
            cursor = await conn.execute("SELECT * FROM relations WHERE status = 'active'")
            relations = await cursor.fetchall()
            cursor = await conn.execute("SELECT * FROM observations WHERE status = 'active'")
            observations = await cursor.fetchall()
            return {
                "entities": [dict(e) for e in entities],
                "relations": [dict(r) for r in relations],
                "observations": [
                    {
                        "entity": o["entity_name"],
                        "content": o["content"],
                        "at": o["timestamp"],
                    }
                    for o in observations
                ],
            }
