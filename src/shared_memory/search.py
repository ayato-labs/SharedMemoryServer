import datetime
import json

from shared_memory.bank import read_bank_data
from shared_memory.database import get_connection
from shared_memory.embeddings import (
    EMBEDDING_MODEL,
    compute_embedding,
    get_gemini_client,
)
from shared_memory.graph import get_graph_data
from shared_memory.utils import batch_cosine_similarity, calculate_importance, log_error


async def perform_search(query: str, limit: int = 10):
    """
    Core RAG Search logic: Semantic Vector Search + Keyword filtering + Reranking.
    """
    conn = get_connection()
    try:
        query_vector = await compute_embedding(query)
        if not query_vector:
            # Fallback to simple keyword search
            return await get_graph_data(query), await read_bank_data(query)

        cursor = conn.cursor()

        # 1. Fetch Candidates (Entities & Bank Files)
        # Using a simple sub-sampling of recently accessed or important items for speed
        candidates = cursor.execute(
            "SELECT content_id, vector FROM embeddings WHERE model_name = ?",
            (EMBEDDING_MODEL,),
        ).fetchall()

        if not candidates:
            return await get_graph_data(query), await read_bank_data(query)

        # 2. Compute Similarities
        c_ids = [c[0] for c in candidates]
        c_vectors = [json.loads(c[1]) for c in candidates]
        similarities = batch_cosine_similarity(query_vector, c_vectors)

        # 3. Apply Metadata Score (Importance + Decay)
        metadata = cursor.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        ).fetchall()
        meta_map = {m[0]: (m[1], m[2]) for m in metadata}

        results = []
        for i, cid in enumerate(c_ids):
            sim = float(similarities[i])
            count, last = meta_map.get(cid, (0, datetime.datetime.now().isoformat()))
            importance = calculate_importance(count, last)

            # Hybrid Score: 70% semantic, 30% importance/recency
            final_score = (sim * 0.7) + (importance * 0.3)
            results.append((cid, final_score))

        # 4. Sort and Filter
        results.sort(key=lambda x: x[1], reverse=True)
        top_cids = [r[0] for r in results[:limit]]

        # 5. Fetch Content for Top Results
        graph_data = await get_graph_data_by_cids(top_cids, conn)
        bank_data = await get_bank_data_by_cids(top_cids, conn)

        return graph_data, bank_data

    except Exception as e:
        log_error(f"Search failed for query: {query}", e)
        return await get_graph_data(query), await read_bank_data(query)
    finally:
        conn.close()


async def get_graph_data_by_cids(cids: list[str], conn):
    if not cids:
        return {"entities": [], "relations": [], "observations": []}
    placeholders = ",".join(["?"] * len(cids))
    entities = conn.execute(
        f"SELECT * FROM entities WHERE name IN ({placeholders})", cids
    ).fetchall()
    obs = conn.execute(
        f"SELECT * FROM observations WHERE entity_name IN ({placeholders})", cids
    ).fetchall()

    matched_names = [r[0] for r in entities]
    relations = []
    if matched_names:
        p2 = ",".join(["?"] * len(matched_names))
        relations = conn.execute(
            f"SELECT * FROM relations WHERE source IN ({p2}) OR target IN ({p2})",
            matched_names + matched_names,
        ).fetchall()

    return {
        "entities": [
            {"name": r[0], "type": r[1], "description": r[2]} for r in entities
        ],
        "relations": [
            {"source": r[0], "target": r[1], "type": r[2]} for r in relations
        ],
        "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in obs],
    }


async def get_bank_data_by_cids(cids: list[str], conn):
    if not cids:
        return {}
    placeholders = ",".join(["?"] * len(cids))
    files = conn.execute(
        f"SELECT filename, content FROM bank_files WHERE filename IN ({placeholders})",
        cids,
    ).fetchall()
    return {f[0]: f[1] for f in files}


async def synthesize_knowledge(entity_name: str):
    """
    Aggregates all known info about an entity and asks Gemini to create a summary.
    """
    conn = get_connection()
    try:
        # Collect Entity, Relations, Observations
        entity = conn.execute(
            "SELECT * FROM entities WHERE name = ?", (entity_name,)
        ).fetchone()
        if not entity:
            return f"Error: Entity '{entity_name}' not found."

        obs = conn.execute(
            "SELECT content, timestamp FROM observations WHERE entity_name = ?",
            (entity_name,),
        ).fetchall()
        rels = conn.execute(
            "SELECT * FROM relations WHERE source = ? OR target = ?",
            (entity_name, entity_name),
        ).fetchall()

        prompt = (
            f"You are a Knowledge Synthesis Engine. Summarize everything known about '{entity_name}'.\n\n"
            f"ENTITIY INFO: {entity[1]} - {entity[2]}\n\n"
            f"OBSERVATIONS:\n" + "\n".join([f"- ({o[1]}) {o[0]}" for o in obs]) + "\n\n"
            "RELATIONS:\n"
            + "\n".join([f"- {r[0]} --({r[2]})--> {r[1]}" for r in rels])
            + "\n\n"
            "Create a concise, structured synthesis of this entity and its role in the project."
        )

        client = get_gemini_client()
        if not client:
            return "Error: Gemini client not available for synthesis."

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        ).text

        return response
    except Exception as e:
        log_error(f"Synthesis failed for {entity_name}", e)
        return f"Error: {e}"
    finally:
        conn.close()
