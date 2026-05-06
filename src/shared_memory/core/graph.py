import asyncio
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from shared_memory.common.config import settings
from shared_memory.common.utils import (
    get_logger,
    log_error,
    mask_sensitive_data,
)
from shared_memory.core.ai_control import AIRateLimiter
from shared_memory.infra.database import async_get_connection
from shared_memory.infra.embeddings import (
    compute_embeddings_bulk,
    get_gemini_client,
)
from shared_memory.infra.llm import get_llm_provider

logger = get_logger("graph")

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", 
    "at", "by", "for", "with",
    "is", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
    "this", "that", "these", "those", "which", "who", "whom", "whose", "where", "how", "why",
    "can", "could", "shall", "should", "will", "would", "may", "might", "must",
    "in", "on", "to", "from", "up", "down", "out", "of", "about", "above", "below", "between",
    "currently", "named", "using", "through", "during", "actually", 
    "basically", "simply"
}


async def extract_hashtags(content: str) -> list[str]:
    """
    Extracts up to 5 relevant hashtags from the content.
    Uses lightweight logic for short text and AI for longer text to optimize performance.
    """
    if not content or len(content) < 10:
        return []

    # Choose strategy based on length
    if len(content) < settings.hashtag_ai_threshold:
        return extract_hashtags_logic(content)
    
    return await extract_hashtags_ai(content)


def extract_hashtags_logic(content: str, max_tags: int = 5) -> list[str]:
    """
    Lightweight keyword extraction using word frequency and stopword filtering.
    """
    # 1. Clean and tokenize (alphanumeric only)
    words = re.findall(r"\w+", content.lower())

    # 2. Filter: length > 3, not a stopword, not purely numeric
    filtered = [
        w for w in words
        if len(w) > 3 and w not in STOP_WORDS and not w.isdigit()
    ]

    # 3. Frequency count
    counts = Counter(filtered)

    # 4. Return top N as normalized hashtags
    return [f"#{word}" for word, _ in counts.most_common(max_tags)]


async def extract_hashtags_ai(content: str) -> list[str]:
    """
    Extracts up to 5 thematic hashtags using AI.
    """
    if not content or len(content) < 10:
        return []

    try:
        provider = get_llm_provider()
        prompt = (
            "Extract up to 5 highly relevant keywords or hashtags from the following text. "
            "Normalize them to lowercase and remove spaces within tags. "
            "Output MUST be a JSON list of strings (e.g. ['#python', '#mcp']).\n\n"
            f"TEXT:\n{content}"
        )

        system_instruction = "You are a specialized keyword extraction engine. Return only a JSON list."
        
        response_text = await provider.generate_content(
            prompt=prompt,
            system_instruction=system_instruction
        )
        # Handle cases where the model might wrap the JSON in code blocks
        clean_json = re.sub(r"```json|```", "", response_text).strip()
        tags = json.loads(clean_json)
        
        if isinstance(tags, list):
            cleaned = []
            for t_raw in tags:
                t_clean = str(t_raw).strip().lower().replace(" ", "")
                if not t_clean.startswith("#"):
                    t_clean = f"#{t_clean}"
                if len(t_clean) > 1:
                    cleaned.append(t_clean)
            return cleaned[:5]
        return []
    except Exception as e:
        logger.warning(f"Hashtag extraction failed: {e}")
        return []


async def save_tags(content_id: str, content_type: str, tags: list[str], conn):
    """
    Saves tags for a piece of knowledge in the tags table.
    Deletes existing tags for the content first to ensure a clean refresh.
    """
    if not tags:
        return

    try:
        # 1. Delete old tags
        await conn.execute(
            "DELETE FROM tags WHERE content_id = ? AND content_type = ?",
            (content_id, content_type)
        )
        # 2. Insert new tags
        data = [(t, content_id, content_type) for t in tags]
        await conn.executemany(
            "INSERT OR IGNORE INTO tags (tag, content_id, content_type) VALUES (?, ?, ?)",
            data
        )
    except Exception as e:
        logger.error(f"Failed to save tags for {content_id}: {e}")


async def check_conflict(entity_name: str, new_contents: list[str], agent_id: str, conn=None):
    """
    Checks if a list of new observations contradicts existing knowledge using the configured LLM.
    Returns a list of (is_conflict, reason) tuples.
    """
    if not new_contents:
        return []

    try:
        logger.info(f"Checking conflicts for entity='{entity_name}' ({len(new_contents)} items)")
        if conn is None:
            async with await async_get_connection() as managed_conn:
                return await _check_conflicts_internal(
                    entity_name, new_contents, agent_id, managed_conn
                )
        else:
            return await _check_conflicts_internal(
                entity_name, new_contents, agent_id, conn
            )
    except Exception as e:
        log_error("Conflict check failed", e)
        raise e


async def _check_conflicts_internal(
    entity_name: str, new_contents: list[str], agent_id: str, conn
):
    # Fetch up to 5 most recent observations for richer context
    cursor = await conn.execute(
        "SELECT content FROM observations WHERE entity_name = ? ORDER BY timestamp DESC LIMIT 5",
        (entity_name,),
    )
    existing = await cursor.fetchall()

    if not existing:
        return [(False, None)] * len(new_contents)

    existing_text = "\n".join([f"- {row[0]}" for row in existing])
    new_text_numbered = "\n".join([f"{i}. {content}" for i, content in enumerate(new_contents)])

    prompt = (
        "You are a Fact-Checking Engine. Check if any of the following NEW statements "
        f"contradict the EXISTING knowledge about '{entity_name}'.\n\n"
        f"EXISTING KNOWLEDGE:\n{existing_text}\n\n"
        f"NEW STATEMENTS:\n{new_text_numbered}\n\n"
        "Output MUST be a JSON list of objects, one for each NEW statement in order:\n"
        '[{"conflict": bool, "reason": "string"}, ...]'
    )

    provider = get_llm_provider()
    system_instruction = "You are a rigorous Fact-Checking Engine. Identify logical contradictions with precision."

    try:
        response_text = await provider.generate_content(
            prompt=prompt,
            system_instruction=system_instruction
        )
        clean_json = re.sub(r"```json|```", "", response_text).strip()
        data = json.loads(clean_json)
        
        results = []
        if isinstance(data, list) and len(data) == len(new_contents):
            results = data
        elif isinstance(data, dict):
            results = [data] * len(new_contents)
        
        if not results:
            return [(False, None)] * len(new_contents)

        final_results = []
        for i, item in enumerate(results):
            is_conflict = item.get("conflict", False)
            reason = item.get("reason") if is_conflict else None
            final_results.append((is_conflict, reason))

            if is_conflict:
                logger.warning(f"CONFLICT DETECTED in '{entity_name}': {reason}")
                await conn.execute(
                    "INSERT INTO conflicts "
                    "(entity_name, existing_content, new_content, reason, agent_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (entity_name, existing_text, new_contents[i], reason, agent_id),
                )
        await conn.commit()
        return final_results
    except Exception as e:
        log_error("Conflict check failed during AI call", e)
        # Record failure as a conflict so a human can decide
        reason = f"Conflict check failed (AI error): {e}"
        for content in new_contents:
            await conn.execute(
                "INSERT INTO conflicts "
                "(entity_name, existing_content, new_content, reason, agent_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (entity_name, existing_text, content, reason, agent_id),
            )
        await conn.commit()
        return [(True, reason)] * len(new_contents)




async def search_by_tags(tags: list[str], conn) -> list[str]:
    """
    Returns content_ids that match ANY of the given tags.
    """
    if not tags:
        return []

    placeholders = ",".join(["?"] * len(tags))
    try:
        cursor = await conn.execute(
            f"SELECT DISTINCT content_id FROM tags WHERE tag IN ({placeholders})",
            tags
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        get_logger("graph").error(f"Tag search failed: {e}")
        return []


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
    logger.info(f"Saving {len(entities)} entities (agent={agent_id})...")
    for e in entities:
        name = str(e.get("name") or "").strip()
        if not name:
            results.append("Error: Entity name is required")
            continue

        e_type = e.get("entity_type", "concept")
        desc = e.get("description", "")
        importance = e.get("importance", 5)

        try:
            importance = max(1, min(10, int(importance)))
        except (ValueError, TypeError):

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
                "model": settings.embedding_model if vector else None,
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
                (name, json.dumps(vector).encode("utf-8"), settings.embedding_model),
            )
        success_count += 1

    msg = f"Saved {success_count} entities (agent={agent_id})"
    if results:
        msg += f" (Errors: {len(results)})"
    logger.info(msg)
    return msg


async def save_relations(relations: list[dict[str, Any]], agent_id: str, conn):
    valid_relations = []
    errors = []
    logger.info(f"Saving {len(relations)} relations (agent={agent_id})...")
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

    msg = f"Saved {len(valid_relations)} relations (agent={agent_id})"
    if errors:
        msg += f" (Errors: {len(errors)})"
    logger.info(msg)
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

    logger.info(f"Saving {len(observations)} observations (agent={agent_id})...")
    for i, o in enumerate(observations):
        entity_name = o.get("entity_name", "").strip()
        content = o.get("content", "").strip()

        if not entity_name or not content:
            errors.append(f"Error: Observation requires entity_name and content: {o}")
            continue

        content = mask_sensitive_data(content)

        # Conflict check
        is_actually_conflict = False
        if precomputed_conflicts is not None:
            # Match conflict from precomputed results if available
            conflict_info = precomputed_conflicts[i] if i < len(precomputed_conflicts) else None
            if conflict_info and conflict_info.get("is_conflict"):
                conflicts_to_report.append(
                    {"entity": entity_name, "reason": conflict_info.get("reason")}
                )
                is_actually_conflict = True
        else:
            results = await check_conflict(entity_name, [content], agent_id, conn=conn)
            if results and results[0][0]:
                is_conflict, reason = results[0]
                conflicts_to_report.append({"entity": entity_name, "reason": reason})
                is_actually_conflict = True

        if is_actually_conflict:
            continue

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

    msg = f"Saved {success_count} observations (agent={agent_id})"
    if errors:
        msg += f" (Errors: {len(errors)})"
    logger.info(msg)
    return msg, conflicts_to_report


async def get_graph_data(query: str | None = None):
    async with await async_get_connection() as conn:
        if query:
            cursor = await conn.execute(
                "SELECT * FROM entities WHERE "
                "(name LIKE ? OR description LIKE ? OR entity_type LIKE ?) AND status = 'active'",
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            )
            matched_entities = await cursor.fetchall()
            entity_matched_names = [e["name"] for e in matched_entities]

            # Also search observations directly
            cursor = await conn.execute(
                "SELECT * FROM observations WHERE content LIKE ? AND status = 'active'",
                (f"%{query}%",),
            )
            direct_observations = await cursor.fetchall()
            obs_matched_entity_names = list(set([o["entity_name"] for o in direct_observations]))

            all_matched_names = list(set(entity_matched_names + obs_matched_entity_names))

            if not all_matched_names:
                return {"entities": [], "relations": [], "observations": []}

            placeholders = ",".join(["?"] * len(all_matched_names))
            cursor = await conn.execute(
                f"SELECT * FROM relations WHERE (subject IN ({placeholders}) "
                f"OR object IN ({placeholders})) AND status = 'active'",
                all_matched_names + all_matched_names,
            )
            relations = await cursor.fetchall()

            # For observations, we take the union of direct matches
            # and those linked to matched entities
            cursor = await conn.execute(
                "SELECT * FROM observations WHERE entity_name IN "
                f"({placeholders}) AND status = 'active'",
                all_matched_names,
            )
            linked_observations = await cursor.fetchall()

            # Combine and de-duplicate observations by content/entity
            final_obs_map = {}
            for o in list(direct_observations) + list(linked_observations):
                key = (o["entity_name"], o["content"])
                if key not in final_obs_map:
                    final_obs_map[key] = o

            final_observations = list(final_obs_map.values())

            return {
                "entities": [dict(e) for e in matched_entities],
                "relations": [dict(r) for r in relations],
                "observations": [
                    {
                        "entity": o["entity_name"],
                        "content": o["content"],
                        "at": o["timestamp"],
                    }
                    for o in final_observations
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
