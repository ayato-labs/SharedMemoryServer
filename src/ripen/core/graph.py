import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from ripen.common.config import settings
from ripen.common.utils import (
    get_logger,
    log_error,
    mask_sensitive_data,
)
from ripen.infra.embeddings import compute_embeddings_bulk
from ripen.infra.llm import get_llm_provider

logger = get_logger("graph")

STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "when",
    "at",
    "by",
    "for",
    "with",
    "is",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "this",
    "that",
    "these",
    "those",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "how",
    "why",
    "can",
    "could",
    "shall",
    "should",
    "will",
    "would",
    "may",
    "might",
    "must",
    "in",
    "on",
    "to",
    "from",
    "up",
    "down",
    "out",
    "of",
    "about",
    "above",
    "below",
    "between",
    "currently",
    "named",
    "using",
    "through",
    "during",
    "actually",
    "basically",
    "simply",
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
    filtered = [w for w in words if len(w) > 3 and w not in STOP_WORDS and not w.isdigit()]

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

        system_instruction = (
            "You are a specialized keyword extraction engine. Return only a JSON list."
        )

        response_text = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
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


async def save_tags(content_id: str, content_type: str, tags: list[str], uow):
    """
    Saves tags for a piece of knowledge in the tags table.
    """
    if not tags:
        return

    try:
        await uow.tags.replace_tags(content_id, content_type, tags)
    except Exception as e:
        logger.error(f"Failed to save tags for {content_id}: {e}")


async def check_conflict(entity_name: str, new_contents: list[str], agent_id: str, uow=None):
    """
    Checks if a list of new observations contradicts existing knowledge.
    """
    if not new_contents:
        return []

    try:
        logger.info(f"Checking conflicts for entity='{entity_name}' ({len(new_contents)} items)")
        if uow is None:
            from ripen.infra.uow import SecureWriteContext

            async with SecureWriteContext() as managed_uow:
                return await _check_conflicts_internal(
                    entity_name, new_contents, agent_id, managed_uow
                )
        else:
            return await _check_conflicts_internal(entity_name, new_contents, agent_id, uow)
    except Exception as e:
        log_error("Conflict check failed", e)
        raise e


async def _check_conflicts_internal(entity_name: str, new_contents: list[str], agent_id: str, uow):
    # Fetch up to 5 most recent observations for richer context
    existing = await uow.observations.get_recent_observations(entity_name, limit=5)

    if not existing:
        return [(False, None)] * len(new_contents)

    existing_text = "\n".join([f"- {row}" for row in existing])
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
    system_instruction = (
        "You are a rigorous Fact-Checking Engine. Identify logical contradictions with precision."
    )

    try:
        response_text = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
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
                await uow.conflicts.insert_conflict(
                    entity_name, existing_text, new_contents[i], reason, agent_id
                )
        return final_results
    except Exception as e:
        log_error("Conflict check failed during AI call", e)
        # Record failure as a conflict so a human can decide
        reason = f"Conflict check failed (AI error): {e}"
        for content in new_contents:
            await uow.conflicts.insert_conflict(
                entity_name, existing_text, content, reason, agent_id
            )
        return [(True, reason)] * len(new_contents)


async def search_by_tags(tags: list[str], uow) -> list[str]:
    """
    Returns content_ids that match ANY of the given tags.
    """
    if not tags:
        return []

    try:
        return await uow.tags.get_content_ids_by_tags(tags)
    except Exception as e:
        get_logger("graph").error(f"Tag search failed: {e}")
        return []


async def save_entities(
    entities: list[dict[str, Any]],
    agent_id: str,
    uow,
    precomputed_vectors: list[list[float]] | None = None,
):
    """
    Saves entities to the database.
    """
    results = []
    success_count = 0

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
        return f"Saved 0 entities (Errors: {len(results)})" if results else "Saved 0 entities"

    if precomputed_vectors is not None:
        vectors = precomputed_vectors
    else:
        embedding_texts = [item["embedding_text"] for item in items_to_process]
        vectors = await compute_embeddings_bulk(embedding_texts)

    for i, item in enumerate(items_to_process):
        name = item["name"]
        e_type = item["type"]
        desc = item["desc"]
        importance = item["importance"]
        vector = vectors[i] if i < len(vectors) else None

        old_row = await uow.entities.get_entity_details(name)
        old_data = json.dumps(old_row) if old_row else None
        action = "UPDATE" if old_row else "INSERT"

        await uow.entities.upsert_entity(name, e_type, desc, importance, agent_id)

        new_data = json.dumps({"name": name, "type": e_type, "desc": desc})
        meta = json.dumps(
            {
                "model": settings.embedding_model if vector else None,
                "has_vector": bool(vector),
                "timestamp": datetime.now().isoformat(),
            }
        )
        await uow.audit.log_action("entities", name, action, old_data, new_data, agent_id, meta)

        if vector:
            await uow.embeddings.upsert_embedding(name, vector, settings.embedding_model)
        success_count += 1

    return f"Saved {success_count} entities (agent={agent_id})"


async def save_relations(relations: list[dict[str, Any]], agent_id: str, uow):
    valid_relations = []
    errors = []
    logger.info(f"Saving {len(relations)} relations (agent={agent_id})...")
    for r in relations:
        subject = (r.get("subject") or r.get("source") or "").strip()
        obj = (r.get("object") or r.get("target") or "").strip()
        predicate = (r.get("predicate") or r.get("relation_type") or "").strip()

        if not all([subject, obj, predicate]):
            errors.append(f"Error: Relation requires subject, object, and predicate: {r}")
            continue
        valid_relations.append((subject, obj, predicate, agent_id))

    if valid_relations:
        await uow.relations.upsert_relations_bulk(valid_relations)

        for subject, obj, predicate, creator in valid_relations:
            await uow.audit.log_action(
                "relations",
                f"{subject}->{predicate}->{obj}",
                "INSERT",
                None,
                json.dumps({"subject": subject, "object": obj, "predicate": predicate}),
                creator,
                json.dumps(
                    {
                        "agent_context": "relation_mapping",
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
            )

    msg = f"Saved {len(valid_relations)} relations (agent={agent_id})"
    if errors:
        msg += f" (Errors: {len(errors)})"
    return msg


async def save_observations(
    observations: list[dict[str, Any]],
    agent_id: str,
    uow,
    precomputed_conflicts: list[dict[str, Any]] | None = None,
):
    """
    Saves observations.
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

        is_actually_conflict = False
        if precomputed_conflicts is not None:
            conflict_info = precomputed_conflicts[i] if i < len(precomputed_conflicts) else None
            if conflict_info and conflict_info.get("is_conflict"):
                conflicts_to_report.append(
                    {"entity": entity_name, "reason": conflict_info.get("reason")}
                )
                is_actually_conflict = True
        else:
            results = await check_conflict(entity_name, [content], agent_id, uow=uow)
            if results and results[0][0]:
                is_actually_conflict = True
                conflicts_to_report.append({"entity": entity_name, "reason": results[0][1]})

        if is_actually_conflict:
            continue

        await uow.observations.insert_observation(entity_name, content, agent_id)
        await uow.entities.increment_importance(entity_name)

        meta = json.dumps(
            {
                "agent_context": "development_trace",
                "timestamp": datetime.now().isoformat(),
            }
        )
        await uow.audit.log_action(
            "observations",
            entity_name,
            "INSERT",
            None,
            json.dumps({"content": content}),
            agent_id,
            meta,
        )
        success_count += 1

    msg = f"Saved {success_count} observations (agent={agent_id})"
    if errors:
        msg += f" (Errors: {len(errors)})"
    return msg, conflicts_to_report


async def get_graph_data(uow=None, limit: int = 20):
    if uow is None:
        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork() as managed_uow:
            return await _get_graph_data_internal(managed_uow, limit)
    return await _get_graph_data_internal(uow, limit)


async def _get_graph_data_internal(uow, limit: int = 20):
    entities, relations, observations = await uow.graph.get_full_graph(limit=limit)
    return {
        "entities": entities,
        "relations": relations,
        "observations": [
            {
                "entity": o["entity_name"],
                "content": o["content"],
                "at": o["timestamp"],
            }
            for o in observations
        ],
        "troubleshooting": [],
    }
