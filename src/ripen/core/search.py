import asyncio
import datetime
import json
import re

from ripen.common.utils import (
    batch_cosine_similarity,
    calculate_importance,
    escape_fts5_query,
    get_logger,
    log_error,
)
from ripen.infra.embeddings import compute_embedding
from ripen.infra.llm import get_llm_provider

logger = get_logger("search")


async def _run_fts_keyword_search(uow, query, fts_query, scored_results):
    fts_sources = [
        (
            "troubleshooting_knowledge",
            "troubleshooting_knowledge_fts",
            "rowid",
            "solution",
            "STABLE",
            2.5,
            "title",
        ),
        ("entities", "entities_fts", "name", "description", "STABLE", 1.5, "name"),
        (
            "observations",
            "observations_fts",
            "entity_name",
            "content",
            "STABLE",
            1.2,
            "entity_name",
        ),
        ("bank_files", "bank_files_fts", "filename", "content", "OBSERVED", 1.0, "filename"),
    ]

    for source_name, fts_table, id_col, content_col, maturity, boost, title_col in fts_sources:
        try:
            if not fts_query:
                raise ValueError("Empty FTS query")

            rows = await uow.search.perform_fts_search(
                fts_table, id_col, content_col, title_col, fts_query
            )
            for row in rows:
                row_id = row[id_col]
                content = row[content_col]
                title = row[title_col]
                rank = list(row.values())[-1]  # bm25 result

                score = max(0.1, abs(rank) * boost)
                if query.lower() in str(row_id).lower() or query.lower() in str(title).lower():
                    score += 15.0

                key = (source_name, row_id)
                current_score, _, _ = scored_results.get(key, (0.0, "", ""))
                scored_results[key] = (current_score + score, str(content), maturity)
        except Exception as e:
            logger.debug(f"FTS search failed for {source_name}, falling back to LIKE: {e}")
            rows = await uow.search.perform_like_search(source_name, id_col, content_col, query)
            for row in rows:
                row_id = row[id_col]
                content = row[content_col]
                key = (source_name, row_id)
                current_score, _, _ = scored_results.get(key, (0.0, "", ""))
                scored_results[key] = (current_score + (2.0 * boost), str(content), maturity)


async def _run_tag_keyword_search(uow, query_words, scored_results):
    rows = await uow.tags.search_tags(query_words)
    for row in rows[:30]:
        cid = row["content_id"]
        ctype = row["content_type"]
        tag = row["tag"]
        score = 15.0
        source_label = ctype + "s" if not ctype.endswith("s") else ctype
        if source_label == "entitys":
            source_label = "entities"

        key = (source_label, cid)
        maturity = "STABLE" if ctype in ["entity", "observation", "troubleshooting"] else "OBSERVED"
        current_score, content, _ = scored_results.get(key, (0.0, f"Matched tag: {tag}", maturity))
        scored_results[key] = (current_score + score, content, maturity)


async def _run_thought_keyword_search(fts_query, exclude_session_id, scored_results):
    try:
        if not fts_query:
            raise ValueError("Empty FTS query")

        from ripen.infra.uow import UnitOfWork

        async with UnitOfWork(is_thoughts=True) as t_uow:
            rows = await t_uow.thoughts.search_thoughts(fts_query, exclude_session_id or "")
            for row in rows:
                sess_id = row["session_id"]
                t_num = row["thought_number"]
                thought = row["thought"]
                rank = list(row.values())[-1]
                score = max(0.1, abs(rank) * 0.3)
                key = ("thought_history", f"{sess_id}#{t_num}")
                current_score, _, _ = scored_results.get(key, (0.0, "", ""))
                scored_results[key] = (current_score + score, str(thought), "TRANSIENT")
    except Exception as e:
        logger.debug(f"FTS5 thought search failed: {e}")


async def perform_keyword_search(
    uow,
    query: str,
    limit: int = 5,
    exclude_session_id: str | None = None,
    include_transient: bool = True,
):
    """
    Improved Keyword Search Logic using FTS5 and maturity-based scoring.
    """
    query_words = re.findall(r"\w+", query.lower())
    if not query_words:
        return []

    scored_results = {}
    fts_query = escape_fts5_query(query)

    # 1. Search Knowledge DB using FTS5
    await _run_fts_keyword_search(uow, query, fts_query, scored_results)

    # 1.1 Search Tags
    await _run_tag_keyword_search(uow, query_words, scored_results)

    # 2. Search Thoughts DB (Transient)
    if include_transient:
        await _run_thought_keyword_search(fts_query, exclude_session_id, scored_results)

    sorted_items = sorted(scored_results.items(), key=lambda x: x[1][0], reverse=True)
    formatted_results = []
    for (source, row_id), (score, content, maturity) in sorted_items[:limit]:
        formatted_results.append(
            {
                "source": source,
                "id": row_id,
                "score": round(score, 2),
                "maturity": maturity,
                "content": content,
            }
        )

    hit_ids = [str(r["id"]) for r in formatted_results]
    await uow.metadata.log_search_stat(query, len(formatted_results), hit_ids=hit_ids)
    return formatted_results


async def perform_search(query: str, uow, limit: int = 10, include_transient: bool = True):
    """Hybrid search logic (Semantic + Keyword)."""
    logger.info(f"perform_search START query={query}")
    start_search = datetime.datetime.now()

    task_vector = asyncio.create_task(compute_embedding(query))
    task_keyword = asyncio.create_task(
        perform_keyword_search(uow, query, include_transient=include_transient)
    )

    try:
        all_rows = await uow.embeddings.get_all_embeddings()

        query_vector = await task_vector
        keyword_results = await task_keyword

        if not query_vector or not all_rows:
            logger.debug(
                f"Embed search skipped or not available. "
                f"query_vector={bool(query_vector)}, all_rows={len(all_rows) if all_rows else 0}"
            )
            return {"entities": [], "relations": [], "observations": [], "troubleshooting": []}, {}

        all_cids = [r["content_id"] for r in all_rows]
        all_vectors = [json.loads(r["vector"]) for r in all_rows]
        similarities = batch_cosine_similarity(query_vector, all_vectors)

        metadata_rows = await uow.metadata.get_all_metadata()
        meta_map = {m["content_id"]: (m["access_count"], m["last_accessed"]) for m in metadata_rows}

        results = []
        seen_cids = set()

        for i, cid in enumerate(all_cids):
            sim = float(similarities[i])
            count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
            importance = calculate_importance(count, last)
            k_res = next((r for r in keyword_results if r["id"] == cid), None)
            k_score = k_res["score"] if k_res else 0.0

            maturity = k_res["maturity"] if k_res else "STABLE"
            maturity_boost = (
                1.5 if maturity == "STABLE" else (0.3 if maturity == "TRANSIENT" else 1.0)
            )

            final_score = ((sim * 0.4) + (importance * 0.15) + (k_score * 0.45)) * maturity_boost
            results.append((cid, final_score))
            seen_cids.add(cid)

        for res in keyword_results:
            cid = res["id"]
            if cid not in seen_cids:
                k_score = res["score"]
                maturity = res["maturity"]
                maturity_boost = (
                    1.5 if maturity == "STABLE" else (0.3 if maturity == "TRANSIENT" else 1.0)
                )

                count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
                importance = calculate_importance(count, last)
                final_score = ((k_score * 0.5) + (importance * 0.5)) * maturity_boost
                results.append((cid, final_score))

        results.sort(key=lambda x: x[1], reverse=True)
        top_results = [r for r in results[:limit] if r[1] > 0.03]
        top_cids = [r[0] for r in top_results]

        for cid in top_cids:
            await uow.metadata.update_access(cid)

        graph_task = asyncio.create_task(get_graph_data_by_cids(top_cids, uow))
        bank_task = asyncio.create_task(get_bank_data_by_cids(top_cids, uow))
        graph_data, bank_data = await asyncio.gather(graph_task, bank_task)

        dur = (datetime.datetime.now() - start_search).total_seconds()
        logger.info(f"perform_search COMPLETE query={query} duration={dur:.3f}s")

        await uow.metadata.log_search_stat(query, len(top_results), hit_ids=top_cids)
        return graph_data, bank_data

    except Exception as e:
        log_error(f"Search failed for query: {query}", e)
        return {"entities": [], "relations": [], "observations": [], "troubleshooting": []}, {}


async def get_graph_data_by_cids(cids: list[str], uow):
    if not cids:
        return {"entities": [], "relations": [], "observations": [], "troubleshooting": []}

    entities = await uow.entities.get_entities_by_names(cids)
    obs = await uow.observations.get_observations_by_entity_names(cids)

    ts_ids = [int(c) for c in cids if str(c).isdigit()]
    ts_rows = await uow.troubleshooting.get_troubleshooting_by_ids(ts_ids)

    matched_names = [e["name"] for e in entities]
    all_relations = await uow.relations.get_relations_by_subjects_or_objects(matched_names)
    relations = all_relations[:30]

    return {
        "entities": [dict(e) for e in entities],
        "relations": [dict(r) for r in relations],
        "observations": [
            {"entity": o["entity_name"], "content": o["content"], "at": o["timestamp"]} for o in obs
        ],
        "troubleshooting": [dict(t) for t in ts_rows],
    }


async def get_bank_data_by_cids(cids: list[str], uow):
    if not cids:
        return {}
    files = await uow.bank.get_bank_files_by_names(cids)
    return {f["filename"]: f["content"] for f in files}


async def search_memory_logic(uow, query: str, limit: int = 10):
    """Compatibility wrapper for system tests."""
    graph_data, bank_data = await perform_search(query, uow, limit)
    return {
        "entities": graph_data["entities"],
        "relations": graph_data["relations"],
        "observations": graph_data["observations"],
        "troubleshooting": graph_data.get("troubleshooting", []),
        "bank_files": bank_data,
    }


async def synthesize_knowledge(entity_name: str, uow):
    """Legacy synthesis function refactored to use LlmProvider."""
    try:
        entity = await uow.entities.get_entity_details(entity_name)
        if not entity:
            return f"Error: Entity '{entity_name}' not found."

        obs = await uow.observations.get_active_observations_by_entity(entity_name)
        rels = await uow.relations.get_relations_by_entity(entity_name)

        provider = get_llm_provider()
        prompt = (
            "You are a Knowledge Synthesis Engine. Summarize everything known about "
            f"'{entity_name}'.\n\n"
            f"ENTITY INFO: {entity['entity_type']} - {entity['description']}\n\n"
            f"OBSERVATIONS:\n"
            + "\n".join([f"- ({o['timestamp']}) {o['content']}" for o in obs])
            + "\n\n"
            "RELATIONS:\n"
            + "\n".join([f"- {r['subject']} --({r['predicate']})--> {r['object']}" for r in rels])
        )

        system_instruction = (
            "You are a high-precision knowledge synthesis engine. "
            "Distill technical facts with absolute accuracy."
        )
        summary = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
        )
        return summary
    except Exception as e:
        logger.error(f"Synthesis failed for {entity_name}: {e}")
        return f"Error: {e}"


async def synthesize_entity_detailed(entity_name: str, observations: list[dict]) -> str:
    """
    Synthesizes multiple observations about an entity into a coherent summary.
    Uses the configured LLM provider (Ollama or Gemini).
    """
    if not observations:
        return f"No observations found for {entity_name}."

    provider = get_llm_provider()
    prompt = f"""
    Entity: {entity_name}
    Observations:
    {json.dumps(observations, indent=2)}

    Task: Create a single, high-density technical summary of this entity based on the observations.
    Identify any conflicts or changes over time.
    Return only the summary.
    """
    system_instruction = (
        "You are a high-precision knowledge synthesis engine. "
        "Distill technical facts with absolute accuracy."
    )

    try:
        summary = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
        )
        return summary
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return f"[Synthesis Error] {e!s}"
