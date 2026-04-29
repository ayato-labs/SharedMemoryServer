import datetime
import json
import re

from shared_memory.bank import read_bank_data
from shared_memory.database import (
    async_get_connection,
    async_get_thoughts_connection,
    log_search_stat,
)
from shared_memory.embeddings import (
    compute_embedding,
    get_gemini_client,
)
from shared_memory.graph import get_graph_data
from shared_memory.utils import (
    batch_cosine_similarity,
    calculate_importance,
    get_logger,
    log_error,
)

logger = get_logger("search")


async def perform_keyword_search(query: str, limit: int = 5, exclude_session_id: str = None):
    """
    Improved Keyword Search Logic:
    - Only searches for ACTIVE status items.
    """
    async with await async_get_connection() as conn:
        query_words = re.findall(r"\w+", query.lower())
        if not query_words:
            return []

        scored_results = {}

        # 1. Search Knowledge DB (Entities, Observations, Bank)
        data_sources = [
            ("entities", "name", "description"),
            ("observations", "entity_name", "content"),
            ("bank_files", "filename", "content"),
        ]

        for table, id_col, content_col in data_sources:
            cursor = await conn.execute(
                f"SELECT {id_col}, {content_col} FROM {table} WHERE status = 'active'"
            )
            for row_id, content in await cursor.fetchall():
                content_lower = str(content).lower()
                row_id_lower = str(row_id).lower()
                score = 0.0

                if query.lower() == row_id_lower:
                    score += 10.0
                elif query.lower() in row_id_lower:
                    score += 5.0

                for word in query_words:
                    if word in content_lower:
                        score += content_lower.count(word) * 1.5

                if score > 0:
                    key = (table, row_id)
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + score, str(content))

        # 2. Search Thoughts DB
        async with await async_get_thoughts_connection() as t_conn:
            t_cursor = await t_conn.execute(
                "SELECT session_id, thought_number, thought "
                "FROM thought_history WHERE session_id != ?",
                (exclude_session_id or "",),
            )
            for sess_id, t_num, thought in await t_cursor.fetchall():
                thought_lower = str(thought).lower()
                score = 0.0
                for word in query_words:
                    if word in thought_lower:
                        score += thought_lower.count(word) * 1.0

                if score > 0:
                    key = ("thought_history", f"{sess_id}#{t_num}")
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + score, str(thought))

        sorted_items = sorted(scored_results.items(), key=lambda x: x[1][0], reverse=True)

        formatted_results = []
        for (source, row_id), (score, content) in sorted_items[:limit]:
            formatted_results.append(
                {
                    "source": source,
                    "id": row_id,
                    "score": round(score, 2),
                    "content": content,
                }
            )

        hit_ids = [r["id"] for r in formatted_results]
        await log_search_stat(query, len(formatted_results), hit_ids=hit_ids)
        return formatted_results


async def perform_search(query: str, limit: int = 10, candidate_limit: int = 20):
    """Hybrid search logic (Semantic + Keyword)."""
    logger.info(f"perform_search START query={query}")
    async with await async_get_connection() as conn:
        try:
            query_vector = await compute_embedding(query, conn=conn)
            if not query_vector:
                return await get_graph_data(query), await read_bank_data(query)

            # Join with entities and bank_files to filter by active status
            cursor = await conn.execute("""
                SELECT e.content_id, e.vector
                FROM embeddings e
                LEFT JOIN entities ent ON e.content_id = ent.name
                LEFT JOIN bank_files bf ON e.content_id = bf.filename
                WHERE (ent.status = 'active' OR bf.status = 'active')
            """)
            all_rows = await cursor.fetchall()

            if not all_rows:
                return await get_graph_data(query), await read_bank_data(query)

            all_cids = [r[0] for r in all_rows]
            all_vectors = [json.loads(r[1]) for r in all_rows]
            similarities = batch_cosine_similarity(query_vector, all_vectors)

            cursor = await conn.execute(
                "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
            )
            metadata = await cursor.fetchall()
            meta_map = {m[0]: (m[1], m[2]) for m in metadata}

            # --- Keyword Search ---
            keyword_results = await perform_keyword_search(query)
            keyword_map = {r["id"]: r["score"] for r in keyword_results}

            results = []
            seen_cids = set()

            # Process all vectors
            for i, cid in enumerate(all_cids):
                sim = float(similarities[i])
                count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
                importance = calculate_importance(count, last)

                # Boost if keyword match exists
                k_score = keyword_map.get(cid, 0.0)
                final_score = (sim * 0.5) + (importance * 0.2) + (k_score * 0.3)

                results.append((cid, final_score))
                seen_cids.add(cid)

            # Add keyword hits that weren't in vectors (unlikely but possible if not yet embedded)
            for cid, k_score in keyword_map.items():
                if cid not in seen_cids:
                    count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
                    importance = calculate_importance(count, last)
                    final_score = (k_score * 0.5) + (importance * 0.5)
                    results.append((cid, final_score))

            results.sort(key=lambda x: x[1], reverse=True)
            # Use candidate_limit for re-ranking population
            top_results = [r for r in results[:candidate_limit] if r[1] > 0.05]
            top_cids = [r[0] for r in top_results]

            graph_data = await get_graph_data_by_cids(top_cids, conn)
            bank_data = await get_bank_data_by_cids(top_cids, conn)

            await log_search_stat(query, len(top_results), hit_ids=top_cids, conn=conn)
            return graph_data, bank_data

        except Exception as e:
            log_error(f"Search failed for query: {query}", e)
            return await get_graph_data(query), await read_bank_data(query)


async def get_graph_data_by_cids(cids: list[str], conn):
    if not cids:
        return {"entities": [], "relations": [], "observations": []}
    placeholders = ",".join(["?"] * len(cids))
    cursor = await conn.execute(
        f"SELECT * FROM entities WHERE name IN ({placeholders}) AND status = 'active'", cids
    )
    entities = await cursor.fetchall()
    cursor = await conn.execute(
        f"SELECT * FROM observations WHERE entity_name IN ({placeholders}) AND status = 'active'",
        cids,
    )
    obs = await cursor.fetchall()

    matched_names = [e["name"] for e in entities]
    relations = []
    if matched_names:
        p2 = ",".join(["?"] * len(matched_names))
        cursor = await conn.execute(
            f"SELECT * FROM relations WHERE (subject IN ({p2}) OR object IN ({p2})) "
            "AND status = 'active'",
            matched_names + matched_names,
        )
        relations = await cursor.fetchall()

    return {
        "entities": [dict(e) for e in entities],
        "relations": [dict(r) for r in relations],
        "observations": [
            {"entity": o["entity_name"], "content": o["content"], "at": o["timestamp"]} for o in obs
        ],
    }


async def get_bank_data_by_cids(cids: list[str], conn):
    if not cids:
        return {}
    placeholders = ",".join(["?"] * len(cids))
    cursor = await conn.execute(
        f"SELECT filename, content FROM bank_files WHERE filename IN ({placeholders}) "
        "AND status = 'active'",
        cids,
    )
    files = await cursor.fetchall()
    return {f["filename"]: f["content"] for f in files}


async def search_memory_logic(query: str, limit: int = 10):
    """Compatibility wrapper for system tests."""
    graph_data, bank_data = await perform_search(query, limit)
    return {
        "entities": graph_data["entities"],
        "relations": graph_data["relations"],
        "observations": graph_data["observations"],
        "bank_files": bank_data,
    }


async def synthesize_knowledge(entity_name: str):
    async with await async_get_connection() as conn:
        try:
            cursor = await conn.execute("SELECT * FROM entities WHERE name = ?", (entity_name,))
            entity = await cursor.fetchone()
            if not entity:
                return f"Error: Entity '{entity_name}' not found."

            cursor = await conn.execute(
                "SELECT content, timestamp FROM observations WHERE entity_name = ? "
                "AND status='active'",
                (entity_name,),
            )
            obs = await cursor.fetchall()
            cursor = await conn.execute(
                "SELECT * FROM relations WHERE (subject = ? OR object = ?) AND status='active'",
                (entity_name, entity_name),
            )
            rels = await cursor.fetchall()

            prompt = (
                "You are a Knowledge Synthesis Engine. Summarize everything known about "
                f"'{entity_name}'.\n\n"
                f"ENTITY INFO: {entity['entity_type']} - {entity['description']}\n\n"
                f"OBSERVATIONS:\n"
                + "\n".join([f"- ({o['timestamp']}) {o['content']}" for o in obs])
                + "\n\n"
                "RELATIONS:\n"
                + "\n".join(
                    [f"- {r['subject']} --({r['predicate']})--> {r['object']}" for r in rels]
                )
            )
            client = get_gemini_client()
            if not client:
                return "Error: Gemini client not available."
            response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            return response.text
        except Exception as e:
            log_error(f"Synthesis failed for {entity_name}", e)
            return f"Error: {e}"
