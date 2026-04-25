import asyncio
import hashlib
import json
import os
import time
from typing import Any

from google import genai

from shared_memory.config import settings
from shared_memory.database import async_get_connection, retry_on_db_lock
from shared_memory.utils import AIRateLimiter, get_logger

logger = get_logger("embeddings")


def _get_text_hash(text: str) -> str:
    """Returns MD5 hash of the text for caching."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_gemini_client():
    """
    Returns a Gemini API client using the key from config or environment.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or settings.api_key
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


async def compute_embeddings_bulk(texts: list[str]) -> list[list[float]]:
    """
    Computes embeddings for a list of strings.
    """
    return await compute_embedding(texts)


@retry_on_db_lock()
async def compute_embedding(
    text_list: str | list[str], conn: Any = None
) -> list[float] | list[list[float]]:
    """
    Computes text embeddings using the Gemini API (Async).
    Handles both single strings and lists of strings.
    """
    # 0. Support for single string input
    is_single = isinstance(text_list, str)
    items = [text_list] if is_single else text_list

    client = get_gemini_client()
    if not client:
        fallback = [([0.0] * 768) for _ in items]
        return fallback[0] if is_single else fallback

    # 1. Filter out empty strings
    valid_entries = []
    for i, txt in enumerate(items):
        if txt and txt.strip():
            valid_entries.append((i, txt[:10000]))

    if not valid_entries:
        fallback = [([0.0] * 768) for _ in items]
        return fallback[0] if is_single else fallback

    logger.info(f"Computing embeddings for {len(items)} items...")
    results = [None] * len(items)
    to_compute = []
    compute_map = []

    async def _process_cache(db):
        for original_idx, txt in valid_entries:
            content_hash = _get_text_hash(txt)
            cursor = await db.execute(
                "SELECT vector FROM embedding_cache WHERE content_hash = ?",
                (content_hash,),
            )
            row = await cursor.fetchone()
            if row:
                results[original_idx] = json.loads(row[0])
            else:
                to_compute.append(txt)
                compute_map.append((original_idx, content_hash))

    if conn:
        # DO NOT use 'async with conn' for already open thread-based connections
        await _process_cache(conn)
    else:
        async with await async_get_connection() as db:
            await _process_cache(db)

    if not to_compute:
        logger.info(f"All {len(items)} embeddings retrieved from CACHE.")
        final_results = [r if r is not None else ([0.0] * 768) for r in results]
        return final_results[0] if is_single else final_results

    logger.info(f"Cache miss: computing {len(to_compute)} new embeddings...")
    start_api = time.perf_counter()

    # Enforce Rate Limiting (Quota Protection)
    await AIRateLimiter.throttle()

    try:
        response = await client.aio.models.embed_content(
            model=settings.embedding_model,
            contents=to_compute,
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            logger.warning("AI Quota Exceeded (429). Retrying after short delay...")
            await asyncio.sleep(2)
            await AIRateLimiter.throttle()
            response = await client.aio.models.embed_content(
                model=settings.embedding_model,
                contents=to_compute,
                config={"task_type": "RETRIEVAL_DOCUMENT"},
            )
        else:
            raise e

    api_duration = time.perf_counter() - start_api
    logger.info(f"Gemini API (Embeddings) COMPLETE. Duration: {api_duration:.2f}s")

    async def _save_cache(db_conn):
        for idx, (original_idx, content_hash) in enumerate(compute_map):
            vector = response.embeddings[idx].values
            results[original_idx] = vector
            await db_conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache
                (content_hash, vector, model_name)
                VALUES (?, ?, ?)
            """,
                (content_hash, json.dumps(vector), settings.embedding_model),
            )
        await db_conn.commit()

    if conn:
        await _save_cache(conn)
    else:
        async with await async_get_connection() as db:
            await _save_cache(db)

    # Ensure all slots are filled
    final_results = [r if r is not None else ([0.0] * 768) for r in results]
    return final_results[0] if is_single else final_results
