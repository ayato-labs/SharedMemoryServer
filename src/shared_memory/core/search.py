import asyncio
import datetime
import json
import re

from shared_memory.common.utils import (
    batch_cosine_similarity,
    calculate_importance,
    get_logger,
    log_error,
)
from shared_memory.core.bank import read_bank_data
from shared_memory.core.graph import get_graph_data
from shared_memory.infra.database import (
    async_get_connection,
    async_get_thoughts_connection,
    log_search_stat,
    update_access,
)
from shared_memory.infra.embeddings import (
    compute_embedding,
    get_gemini_client,
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

        # 1. Search Knowledge DB using FTS5 (Entities, Observations, Bank)
        fts_sources = [
            ("entities_fts", "entities", "name", "description"),
            ("observations_fts", "observations", "entity_name", "content"),
            ("bank_files_fts", "bank_files", "filename", "content"),
        ]

        for fts_table, source_name, id_col, content_col in fts_sources:
            try:
                # Use MATCH for fast full-text searching and BM25 for ranking
                cursor = await conn.execute(
                    f"SELECT {id_col}, {content_col}, bm25({fts_table}) "
                    f"FROM {fts_table} WHERE {fts_table} MATCH ?",
                    (query,)
                )
                for row_id, content, rank in await cursor.fetchall():
                    # BM25 returns smaller values for better matches; 
                    # we convert it to a positive score (higher is better)
                    score = max(0.1, abs(rank) * 1.5)
                    
                    # Boost if the query is an exact match for the ID/Name
                    if query.lower() == str(row_id).lower():
                        score += 15.0

                    key = (source_name, row_id)
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + score, str(content))
            except Exception as e:
                logger.debug(f"FTS5 search failed for {fts_table}: {e}")
                # Fallback to a simpler LIKE if FTS fails for some reason
                cursor = await conn.execute(
                    f"SELECT {id_col}, {content_col} FROM {source_name} "
                    f"WHERE ({content_col} LIKE ? OR {id_col} LIKE ?) AND status = 'active'",
                    (f"%{query}%", f"%{query}%")
                )
                for row_id, content in await cursor.fetchall():
                    key = (source_name, row_id)
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + 2.0, str(content))

        # 1.1 Search Tags
        placeholders = ",".join(["?"] * len(query_words))
        cursor = await conn.execute(
            f"SELECT content_id, content_type, tag FROM tags WHERE tag IN ({placeholders})",
            [f"#{w}" for w in query_words]
        )
        for cid, ctype, tag in await cursor.fetchall():
            score = 15.0  # High score for explicit tag match
            key = (ctype + "s" if not ctype.endswith("s") else ctype, cid)
            current_score, content = scored_results.get(key, (0.0, f"Matched tag: {tag}"))
            scored_results[key] = (current_score + score, content)

        # 2. Search Thoughts DB using FTS5
        try:
            async with await async_get_thoughts_connection() as t_conn:
                t_cursor = await t_conn.execute(
                    "SELECT session_id, thought_number, thought, bm25(thought_history_fts) "
                    "FROM thought_history_fts WHERE thought_history_fts MATCH ? "
                    "AND session_id != ?",
                    (query, exclude_session_id or ""),
                )
                for sess_id, t_num, thought, rank in await t_cursor.fetchall():
                    score = max(0.1, abs(rank) * 1.0)
                    key = ("thought_history", f"{sess_id}#{t_num}")
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + score, str(thought))
        except Exception as e:
            logger.debug(f"FTS5 thought search failed: {e}")
            # Fallback for thoughts
            async with await async_get_thoughts_connection() as t_conn:
                t_cursor = await t_conn.execute(
                    "SELECT session_id, thought_number, thought FROM thought_history "
                    "WHERE thought LIKE ? AND session_id != ?",
                    (f"%{query}%", exclude_session_id or ""),
                )
                for sess_id, t_num, thought in await t_cursor.fetchall():
                    key = ("thought_history", f"{sess_id}#{t_num}")
                    current_score, _ = scored_results.get(key, (0.0, ""))
                    scored_results[key] = (current_score + 1.5, str(thought))

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
    """Hybrid search logic (Semantic + Keyword) - Optimized with parallelism."""
    logger.info(f"perform_search START query={query}")
    start_search = datetime.datetime.now()
    
    # --- Parallel Step 1: Trigger long-running tasks ---
    # We run embedding computation and keyword search in parallel.
    # Note: compute_embedding uses external API (Gemini), keyword search uses SQLite.
    task_vector = asyncio.create_task(compute_embedding(query))
    task_keyword = asyncio.create_task(perform_keyword_search(query))

    try:
        async with await async_get_connection() as conn:
            # --- Parallel Step 2: Fetch current embeddings while waiting for tasks ---
            # This fetches the entire embedding map for similarity calculation.
            cursor = await conn.execute("""
                SELECT e.content_id, e.vector
                FROM embeddings e
                LEFT JOIN entities ent ON e.content_id = ent.name
                LEFT JOIN bank_files bf ON e.content_id = bf.filename
                WHERE (ent.status = 'active' OR bf.status = 'active')
            """)
            all_rows = await cursor.fetchall()

            # --- Step 3: Wait for parallel tasks to complete ---
            query_vector = await task_vector
            keyword_results = await task_keyword
            
            if not query_vector:
                # Fallback to basic search if embedding fails
                return await get_graph_data(query), await read_bank_data(query)

            if not all_rows:
                return await get_graph_data(query), await read_bank_data(query)

            # --- Step 4: Compute similarity and combine results ---
            all_cids = [r[0] for r in all_rows]
            all_vectors = [json.loads(r[1]) for r in all_rows]
            similarities = batch_cosine_similarity(query_vector, all_vectors)

            cursor = await conn.execute(
                "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
            )
            metadata = await cursor.fetchall()
            meta_map = {m[0]: (m[1], m[2]) for m in metadata}

            keyword_map = {r["id"]: r["score"] for r in keyword_results}

            results = []
            seen_cids = set()

            for i, cid in enumerate(all_cids):
                sim = float(similarities[i])
                count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
                importance = calculate_importance(count, last)

                k_score = keyword_map.get(cid, 0.0)
                # Weighted fusion (Semantic 40%, Keyword 30%, Importance 15%, Tag Match 15%)
                # Tags are already partially in k_score but we could boost them here if needed.
                final_score = (sim * 0.4) + (importance * 0.15) + (k_score * 0.45)

                results.append((cid, final_score))
                seen_cids.add(cid)

            for cid, k_score in keyword_map.items():
                if cid not in seen_cids:
                    count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
                    importance = calculate_importance(count, last)
                    final_score = (k_score * 0.5) + (importance * 0.5)
                    results.append((cid, final_score))

            results.sort(key=lambda x: x[1], reverse=True)
            # Step 5: Respect the limit and filter by threshold
            top_results = [r for r in results[:limit] if r[1] > 0.05]
            top_cids = [r[0] for r in top_results]

            # Update access for top results
            for cid in top_cids:
                await update_access(cid, conn=conn)

            # Fetch detailed data in parallel
            graph_task = asyncio.create_task(get_graph_data_by_cids(top_cids, conn))
            bank_task = asyncio.create_task(get_bank_data_by_cids(top_cids, conn))
            
            graph_data, bank_data = await asyncio.gather(graph_task, bank_task)

            dur = (datetime.datetime.now() - start_search).total_seconds()
            logger.info(f"perform_search COMPLETE query={query} duration={dur:.3f}s")
            
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
