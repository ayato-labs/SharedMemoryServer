import hashlib
import json
import os

from google import genai

from shared_memory.database import async_get_connection, retry_on_db_lock
from shared_memory.utils import get_logger, log_error, log_info

from shared_memory.config import settings

logger = get_logger("embeddings")

EMBEDDING_MODEL = settings.embedding_model
DIMENSIONALITY = settings.dimensionality


def _get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@retry_on_db_lock()
async def _get_cached_embedding(text_hash: str, conn=None) -> list[float] | None:
    logger.debug(
        f"_get_cached_embedding START hash={text_hash[:8]} "
        f"reuse_conn={conn is not None}"
    )

    async def _execute(c):
        logger.debug(f"_get_cached_embedding EXECUTING hash={text_hash[:8]}")
        cursor = await c.execute(
            "SELECT vector FROM embedding_cache WHERE "
            "content_hash = ? AND model_name = ?",
            (text_hash, EMBEDDING_MODEL),
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row[0].decode("utf-8"))
        return None

    if conn:
        return await _execute(conn)

    async with await async_get_connection() as c:
        logger.debug(f"DB Connection ACQUIRED hash={text_hash[:8]}")
        return await _execute(c)


@retry_on_db_lock()
async def _save_to_cache(text_hash: str, vector: list[float], conn=None):
    vector_json = json.dumps(vector).encode("utf-8")

    async def _execute(c):
        await c.execute(
            "INSERT OR REPLACE INTO embedding_cache "
            "(content_hash, vector, model_name) VALUES (?, ?, ?)",
            (text_hash, vector_json, EMBEDDING_MODEL),
        )
        await c.commit()

    if conn:
        await _execute(conn)
    else:
        async with await async_get_connection() as c:
            await _execute(c)


def get_gemini_client() -> genai.Client | None:
    """
    Retrieves a Gemini API client using the centralized config.
    """
    api_key = settings.api_key
    if not api_key:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        log_error("Failed to initialize Gemini client", e)
        return None


async def compute_embedding(text: str, conn=None) -> list[float] | None:
    """Computes embedding with local caching."""
    logger.debug(
        f"compute_embedding START text={text[:20]}... reuse_conn={conn is not None}"
    )
    text_hash = _get_text_hash(text)
    cached = await _get_cached_embedding(text_hash, conn=conn)
    if cached:
        return cached

    client = get_gemini_client()
    if not client:
        return None

    try:
        # ASYNC TRANSITION: Use client.aio for non-blocking I/O
        response = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": DIMENSIONALITY},
        )
        vector = response.embeddings[0].values
        await _save_to_cache(text_hash, vector, conn=conn)
        return vector
    except Exception as e:
        log_error(f"Embedding computation failed for: {text[:50]}...", e)
        return None


async def compute_embeddings_bulk(texts: list[str]) -> list[list[float] | None]:
    """Computes multiple embeddings in parallel with caching."""
    results = []
    to_compute = []
    indices = []

    for i, text in enumerate(texts):
        text_hash = _get_text_hash(text)
        cached = await _get_cached_embedding(text_hash)
        if cached:
            results.append(cached)
        else:
            results.append(None)
            to_compute.append(text)
            indices.append(i)

    if not to_compute:
        return results

    client = get_gemini_client()
    if not client:
        return results

    try:
        # ASYNC TRANSITION: Use client.aio for non-blocking I/O
        response = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=to_compute,
            config={"output_dimensionality": DIMENSIONALITY},
        )
        for i, emb in enumerate(response.embeddings):
            vector = emb.values
            await _save_to_cache(_get_text_hash(to_compute[i]), vector)
            results[indices[i]] = vector
    except Exception as e:
        log_error("Bulk embedding computation failed", e)

    return results
