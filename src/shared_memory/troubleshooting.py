import json
import math
from datetime import datetime
from typing import Any

from shared_memory.database import get_connection, retry_on_db_lock
from shared_memory.embeddings import compute_embedding
from shared_memory.utils import cosine_similarity, log_error

# Scoring Hyper-parameters
DECAY_RATE = 0.0001  # Penalty per minute
USAGE_BOOST = 0.2  # Boost per log(1 + access_count)


@retry_on_db_lock()
async def save_troubleshooting_record(
    title: str,
    solution: str,
    affected_functions: str | None = None,
    env_metadata: dict[str, Any] | None = None,
) -> int:
    """
    Saves a troubleshooting record and its embedding.
    """
    conn = get_connection()
    cursor = conn.cursor()

    env_json = json.dumps(env_metadata) if env_metadata else None

    try:
        # 1. Insert into troubleshooting_knowledge
        cursor.execute(
            """
            INSERT INTO troubleshooting_knowledge (title, solution, affected_functions, env_metadata)
            VALUES (?, ?, ?, ?)
        """,
            (title, solution, affected_functions, env_json),
        )
        record_id = cursor.lastrowid

        # 2. Compute embedding for search (Title + snippet of solution)
        search_text = f"{title}\n{solution[:500]}"
        vector = await compute_embedding(search_text)

        if vector:
            content_id = f"ts_{record_id}"
            vector_blob = json.dumps(vector).encode("utf-8")
            cursor.execute(
                """
                INSERT INTO embeddings (content_id, vector, model_name)
                VALUES (?, ?, ?)
                ON CONFLICT(content_id) DO UPDATE SET
                    vector = excluded.vector,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (content_id, vector_blob, "gemini-embedding-001"),
            )

        conn.commit()
        return record_id
    except Exception as e:
        log_error(f"Failed to save troubleshooting record: {title}", e)
        conn.rollback()
        raise
    finally:
        conn.close()


@retry_on_db_lock()
async def search_troubleshooting_history(
    query: str, limit: int = 5
) -> list[dict[str, Any]]:
    """
    Searches troubleshooting history using Semantic Search + Time Decay + Usage Boost.
    """
    query_vector = await compute_embedding(query)
    if not query_vector:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Get all records with embeddings
        cursor.execute("""
            SELECT ts.id, ts.title, ts.solution, ts.env_metadata, ts.access_count, ts.created_at, e.vector
            FROM troubleshooting_knowledge ts
            JOIN embeddings e ON e.content_id = 'ts_' || ts.id
        """)

        results = []
        now = datetime.now()

        for row in cursor.fetchall():
            (
                rec_id,
                title,
                solution,
                env_json,
                access_count,
                created_at_str,
                vector_blob,
            ) = row

            # Parse vector
            try:
                vector = json.loads(vector_blob.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                continue

            # Calculate Base Similarity
            similarity = cosine_similarity(query_vector, vector)

            # Calculate Time Decay
            try:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                created_at = now

            delta_minutes = (now - created_at).total_seconds() / 60
            time_decay = math.exp(-DECAY_RATE * delta_minutes)

            # Calculate Usage Boost
            usage_boost = 1.0 + USAGE_BOOST * math.log1p(access_count)

            # Final Reranking Score
            final_score = similarity * time_decay * usage_boost

            results.append(
                {
                    "id": rec_id,
                    "title": title,
                    "solution": solution,
                    "env_metadata": json.loads(env_json) if env_json else {},
                    "score": final_score,
                    "created_at": created_at_str,
                    "access_count": access_count,
                }
            )

        # 2. Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:limit]

        # 3. Increment access count for top results (async logic usually, but here we do it simple)
        for res in top_results:
            cursor.execute(
                "UPDATE troubleshooting_knowledge SET access_count = access_count + 1 WHERE id = ?",
                (res["id"],),
            )

        conn.commit()
        return top_results

    except Exception as e:
        log_error(f"Search failed for query: {query}", e)
        return []
    finally:
        conn.close()
