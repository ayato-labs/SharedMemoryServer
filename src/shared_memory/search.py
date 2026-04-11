import datetime
import json
import re

from shared_memory.bank import read_bank_data
from shared_memory.database import async_get_connection, async_get_thoughts_connection
from shared_memory.embeddings import (
    EMBEDDING_MODEL,
    compute_embedding,
    get_gemini_client,
)
from shared_memory.graph import get_graph_data
from shared_memory.utils import (
    batch_cosine_similarity,
    calculate_importance,
    log_error,
)
from shared_memory.database import (
    async_get_connection,
    async_get_thoughts_connection,
    log_search_stat,
)


async def perform_keyword_search(
    query: str, limit: int = 5, exclude_session_id: str = None
):
    """
    Improved Keyword Search Logic:
    - Exact matches in ID/Name: 10.0
    - Partial matches in ID/Name: 5.0
    - Keyword frequency in content: 1.5 per occurrence
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
            cursor = await conn.execute(f"SELECT {id_col}, {content_col} FROM {table}")
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
                    scored_results[(table, row_id)] = (
                        scored_results.get((table, row_id), 0.0) + score
                    )

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
                    scored_results[key] = scored_results.get(key, 0.0) + score

        # Sort and format
        sorted_items = sorted(scored_results.items(), key=lambda x: x[1], reverse=True)

        formatted_results = []
        for (source, row_id), score in sorted_items[:limit]:
            formatted_results.append(
                {"source": source, "id": row_id, "score": round(score, 2)}
            )

        # Log search statistics for ROI/Hit-rate calculation
        await log_search_stat(query, len(formatted_results))

        return formatted_results


async def perform_search(query: str, limit: int = 10):
    """
    Core RAG Search logic: Semantic Vector Search + Keyword filtering + Reranking.
    """
    async with await async_get_connection() as conn:
        try:
            query_vector = await compute_embedding(query)
            if not query_vector:
                # Fallback to simple keyword search
                return await get_graph_data(query), await read_bank_data(query)

            # 1. Fetch Candidates (Entities & Bank Files)
            cursor = await conn.execute(
                "SELECT content_id, vector FROM embeddings WHERE model_name = ?",
                (EMBEDDING_MODEL,),
            )
            candidates = await cursor.fetchall()

            if not candidates:
                return await get_graph_data(query), await read_bank_data(query)

            # 2. Compute Similarities
            c_ids = [c[0] for c in candidates]
            c_vectors = [json.loads(c[1]) for c in candidates]
            similarities = batch_cosine_similarity(query_vector, c_vectors)

            # 3. Apply Metadata Score (Importance + Decay)
            cursor = await conn.execute(
                "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
            )
            metadata = await cursor.fetchall()
            meta_map = {m[0]: (m[1], m[2]) for m in metadata}

            results = []
            for i, cid in enumerate(c_ids):
                sim = float(similarities[i])
                count, last = meta_map.get(
                    cid, (0, datetime.datetime.now().isoformat())
                )
                importance = calculate_importance(count, last)

                # Hybrid Score: 70% semantic, 30% importance/recency
                final_score = (sim * 0.7) + (importance * 0.3)
                results.append((cid, final_score))

            # 4. Sort and Filter
            results.sort(key=lambda x: x[1], reverse=True)
            # Apply a loose threshold to exclude obvious non-matches from "Hits"
            top_results = [r for r in results[:limit] if r[1] > 0.4]
            top_cids = [r[0] for r in top_results]

            # 5. Fetch Content for Top Results
            graph_data = await get_graph_data_by_cids(top_cids, conn)
            bank_data = await get_bank_data_by_cids(top_cids, conn)

            # Log search statistics
            hit_count = len(graph_data["entities"]) + len(bank_data)
            await log_search_stat(query, hit_count)

            return graph_data, bank_data

        except Exception as e:
            log_error(f"Search failed for query: {query}", e)
            return await get_graph_data(query), await read_bank_data(query)


async def get_graph_data_by_cids(cids: list[str], conn):
    if not cids:
        return {"entities": [], "relations": [], "observations": []}
    placeholders = ",".join(["?"] * len(cids))
    cursor = await conn.execute(
        f"SELECT * FROM entities WHERE name IN ({placeholders})", cids
    )
    entities = await cursor.fetchall()
    cursor = await conn.execute(
        f"SELECT * FROM observations WHERE entity_name IN ({placeholders})", cids
    )
    obs = await cursor.fetchall()

    # Track usage (Reuse Fact)
    for cid in cids:
        from shared_memory.database import update_access
        await update_access(cid, conn=conn)

    matched_names = [r[0] for r in entities]
    relations = []
    if matched_names:
        p2 = ",".join(["?"] * len(matched_names))
        cursor = await conn.execute(
            f"SELECT * FROM relations WHERE subject IN ({p2}) OR object IN ({p2})",
            matched_names + matched_names,
        )
        relations = await cursor.fetchall()

    return {
        "entities": [
            {"name": r[0], "type": r[1], "description": r[2]} for r in entities
        ],
        "relations": [
            {"subject": r[0], "object": r[1], "predicate": r[2]} for r in relations
        ],
        "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in obs],
    }


async def get_bank_data_by_cids(cids: list[str], conn):
    if not cids:
        return {}
    placeholders = ",".join(["?"] * len(cids))
    cursor = await conn.execute(
        f"SELECT filename, content FROM bank_files WHERE filename IN ({placeholders})",
        cids,
    )
    files = await cursor.fetchall()
    
    # Track usage (Reuse Fact)
    for cid in cids:
        from shared_memory.database import update_access
        await update_access(cid, conn=conn)

    return {f[0]: f[1] for f in files}


async def synthesize_knowledge(entity_name: str):
    """
    Aggregates all known info about an entity and asks Gemini to create a summary.
    """
    async with await async_get_connection() as conn:
        try:
            # Collect Entity, Relations, Observations
            cursor = await conn.execute(
                "SELECT * FROM entities WHERE name = ?", (entity_name,)
            )
            entity = await cursor.fetchone()
            if not entity:
                return f"Error: Entity '{entity_name}' not found."

            cursor = await conn.execute(
                "SELECT content, timestamp FROM observations WHERE entity_name = ?",
                (entity_name,),
            )
            obs = await cursor.fetchall()
            cursor = await conn.execute(
                "SELECT * FROM relations WHERE subject = ? OR object = ?",
                (entity_name, entity_name),
            )
            rels = await cursor.fetchall()

            prompt = (
                "You are a Knowledge Synthesis Engine. "
                f"Summarize everything known about '{entity_name}'.\n\n"
                f"ENTITIY INFO: {entity[1]} - {entity[2]}\n\n"
                f"OBSERVATIONS:\n"
                + "\n".join([f"- ({o[1]}) {o[0]}" for o in obs])
                + "\n\n"
                "RELATIONS:\n"
                + "\n".join([f"- {r[0]} --({r[2]})--> {r[1]}" for r in rels])
                + "\n\n"
                "Create a concise, structured synthesis of this entity and "
                "its role in the project."
            )

            client = get_gemini_client()
            if not client:
                return "Error: Gemini client not available for synthesis."

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
            )

            return response.text
        except Exception as e:
            log_error(f"Synthesis failed for {entity_name}", e)
            return f"Error: {e}"
