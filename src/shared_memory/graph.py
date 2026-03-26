import json
from typing import Any

from shared_memory.database import get_connection, update_access
from shared_memory.embeddings import (
    EMBEDDING_MODEL,
    compute_embeddings_bulk,
    get_gemini_client,
)
from shared_memory.utils import mask_sensitive_data


async def check_conflict(entity_name: str, new_content: str, agent_id: str, conn=None):
    """
    Internal helper to check if new content contradicts existing observations using LLM.
    Returns (conflict_found: bool, reason: str)
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        # Fetch up to 3 most recent observations for context
        existing = conn.execute(
            "SELECT content FROM observations WHERE entity_name = ? ORDER BY timestamp DESC LIMIT 3",
            (entity_name,),
        ).fetchall()
        if not existing:
            return False, None

        existing_text = "\n".join([f"- {row[0]}" for row in existing])
        prompt = (
            f"You are a Fact-Checking Engine. Check if the following NEW statement contradicts "
            f"the EXISTING knowledge about '{entity_name}'.\n\n"
            f"EXISTING KNOWLEDGE:\n{existing_text}\n\n"
            f"NEW STATEMENT:\n{new_content}\n\n"
            f"Is there a direct contradiction? Respond ONLY with a JSON object:\n"
            f'{{"conflict": true/false, "reason": "explanation if true, else empty"}}'
        )

        client = get_gemini_client()
        if not client:
            return False, None

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        ).text

        # Parse JSON from response (handling potential markdown formatting)
        clean_res = response.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_res)

        if data.get("conflict"):
            # Log to DB
            conn.execute(
                "INSERT INTO conflicts (entity_name, existing_content, new_content, reason, agent_id) VALUES (?, ?, ?, ?, ?)",
                (entity_name, existing_text, new_content, data.get("reason"), agent_id),
            )
            conn.commit()
            return True, data.get("reason")

        return False, None
    finally:
        if should_close:
            conn.close()


async def save_entities(entities: list[dict[str, Any]], agent_id: str, conn):
    results = []
    success_count = 0
    # 1. Pre-process and collect texts for bulk embedding
    items_to_process = []
    for e in entities:
        name = e.get("name", "").strip()
        if not name:
            results.append("Error: Entity name is required")
            continue

        e_type = e.get("entity_type", "concept")
        desc = e.get("description", "")
        importance = e.get("importance", 5)

        # Basic range check
        try:
            importance = max(1, min(10, int(importance)))
        except (ValueError, TypeError):
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
        msg = "Saved 0 entities"
        if results:
            msg += f" (Errors: {len(results)})"
        return msg

    # 2. Bulk Compute Embeddings
    embedding_texts = [item["embedding_text"] for item in items_to_process]
    vectors = await compute_embeddings_bulk(embedding_texts)

    # 3. Synchronize DB
    for i, item in enumerate(items_to_process):
        name = item["name"]
        e_type = item["type"]
        desc = item["desc"]
        importance = item["importance"]
        vector = vectors[i]

        # Audit: Fetch old state
        old_row = conn.execute(
            "SELECT name, entity_type, description FROM entities WHERE name = ?",
            (name,),
        ).fetchone()

        # INSERT OR REPLACE
        conn.execute(
            "INSERT OR REPLACE INTO entities (name, entity_type, description, importance, updated_by) VALUES (?, ?, ?, ?, ?)",
            (name, e_type, desc, importance, agent_id),
        )

        # Record Audit
        action = "UPDATE" if old_row else "INSERT"
        old_data = (
            json.dumps({"name": old_row[0], "type": old_row[1], "desc": old_row[2]})
            if old_row
            else None
        )
        new_data = json.dumps({"name": name, "type": e_type, "desc": desc})
        conn.execute(
            "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("entities", name, action, old_data, new_data, agent_id),
        )

        # Vector Sync
        if vector:
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
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
        source = r.get("source", "").strip()
        target = r.get("target", "").strip()
        r_type = r.get("relation_type", "").strip()

        if not all([source, target, r_type]):
            errors.append(f"Error: Relation requires source, target, and type: {r}")
            continue
        valid_relations.append((source, target, r_type, agent_id))

    if valid_relations:
        conn.executemany(
            "INSERT OR REPLACE INTO relations (source, target, relation_type, created_by) VALUES (?, ?, ?, ?)",
            valid_relations,
        )

    msg = f"Saved {len(valid_relations)} relations"
    if errors:
        msg += f" (Errors: {len(errors)})"
    return msg


async def save_observations(observations: list[dict[str, Any]], agent_id: str, conn):
    conflicts_found = []
    errors = []
    for o in observations:
        entity_name = o.get("entity_name", "").strip()
        content = o.get("content", "").strip()

        if not entity_name or not content:
            errors.append(f"Error: Observation requires entity_name and content: {o}")
            continue

        content = mask_sensitive_data(content)

        is_conflict, reason = await check_conflict(
            entity_name, content, agent_id, conn=conn
        )
        if is_conflict:
            conflicts_found.append({"entity": entity_name, "reason": reason})

        conn.execute(
            "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
            (entity_name, content, agent_id),
        )
        conn.execute(
            "UPDATE entities SET importance = MIN(importance + 1, 10), updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (entity_name,),
        )
        conn.execute(
            "INSERT INTO audit_logs (table_name, content_id, action, new_data, agent_id) VALUES (?, ?, ?, ?, ?)",
            (
                "observations",
                entity_name,
                "INSERT",
                json.dumps({"content": content}),
                agent_id,
            ),
        )
    return f"Saved {len(observations)} observations", conflicts_found


async def get_graph_data(query: str | None = None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if query:
            q = f"%{query}%"
            e_rows = cursor.execute(
                "SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?", (q, q)
            ).fetchall()
            o_rows = cursor.execute(
                "SELECT * FROM observations WHERE content LIKE ?", (q,)
            ).fetchall()

            for row in e_rows:
                await update_access(row[0], conn)

            matched_names = [r[0] for r in e_rows]
            relations = []
            if matched_names:
                placeholders = ",".join(["?"] * len(matched_names))
                relations = cursor.execute(
                    f"SELECT * FROM relations WHERE source IN ({placeholders}) OR target IN ({placeholders})",
                    matched_names + matched_names,
                ).fetchall()

            return {
                "entities": [
                    {"name": r[0], "type": r[1], "description": r[2]} for r in e_rows
                ],
                "relations": [
                    {"source": r[0], "target": r[1], "type": r[2]} for r in relations
                ],
                "observations": [
                    {"entity": o[1], "content": o[2], "at": o[3]} for o in o_rows
                ],
            }
        else:
            entities = cursor.execute("SELECT * FROM entities").fetchall()
            relations = cursor.execute("SELECT * FROM relations").fetchall()
            obs = cursor.execute("SELECT * FROM observations").fetchall()
            return {
                "entities": [
                    {"name": e[0], "type": e[1], "description": e[2]} for e in entities
                ],
                "relations": [
                    {"source": r[0], "target": r[1], "type": r[2]} for r in relations
                ],
                "observations": [
                    {"entity": o[1], "content": o[2], "at": o[3]} for o in obs
                ],
            }
    finally:
        conn.close()
