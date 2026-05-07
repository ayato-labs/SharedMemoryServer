import hashlib
import json
from typing import Any

from shared_memory.common.config import settings
from shared_memory.common.utils import get_logger, normalize_text
from shared_memory.core.ai_control import AIRateLimiter, retry_on_ai_quota
from shared_memory.infra.database import async_get_connection, retry_on_db_lock

logger = get_logger("embeddings")

# Lazy load fastembed to avoid overhead if not used
_fastembed_model = None


def get_fastembed_model():
    global _fastembed_model
    if _fastembed_model is None:
        try:
            from fastembed import TextEmbedding

            logger.info(f"Initializing FastEmbed with model: {settings.embedding_model}")
            _fastembed_model = TextEmbedding(model_name=settings.embedding_model)
        except ImportError:
            logger.error("fastembed not installed. Please install it to use local embeddings.")
            raise
    return _fastembed_model


def get_gemini_client():
    """
    Returns a Gemini API client using the key from config or environment.
    """
    from google import genai

    api_key = settings.api_key
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


async def compute_embeddings_bulk(texts: list[str]) -> list[list[float]]:
    """
    Computes embeddings for a list of strings.
    """
    return await compute_embedding(texts)


@retry_on_ai_quota(max_retries=3, rotate_models=False)
@retry_on_db_lock()
async def compute_embedding(
    text_list: str | list[str], conn: Any = None
) -> list[float] | list[list[float]]:
    """
    Computes text embeddings using the configured engine (FastEmbed or Gemini).
    """
    is_single = isinstance(text_list, str)
    items = [text_list] if is_single else text_list

    # 1. Normalize and filter
    valid_entries = []
    for i, raw_txt in enumerate(items):
        clean_txt = normalize_text(raw_txt)
        if clean_txt:
            valid_entries.append((i, clean_txt))

    if not valid_entries:
        # Return dummy vectors if no text
        dim = 384 if settings.embedding_engine == "fastembed" else 768
        fallback = [([0.0] * dim) for _ in items]
        return fallback[0] if is_single else fallback

    logger.info(f"Computing embeddings for {len(items)} items using {settings.embedding_engine}...")
    results = [None] * len(items)
    to_compute = []
    compute_map = []

    # Cache key includes model name to prevent collisions between different engines
    model_name = settings.embedding_model
    logger.debug(f"Checking cache for {len(valid_entries)} entries using model {model_name}")

    async def _process_cache(db):
        for original_idx, txt in valid_entries:
            content_hash = _get_text_hash(txt)
            cursor = await db.execute(
                "SELECT vector FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
                (content_hash, model_name),
            )
            row = await cursor.fetchone()
            if row:
                results[original_idx] = json.loads(row[0])
            else:
                to_compute.append(txt)
                compute_map.append((original_idx, content_hash))

    if conn:
        await _process_cache(conn)
    else:
        async with await async_get_connection() as db:
            await _process_cache(db)

    if not to_compute:
        logger.info(f"All {len(items)} embeddings retrieved from CACHE (SHA-256).")
        dim = 384 if settings.embedding_engine == "fastembed" else 768
        final_results = [r if r is not None else ([0.0] * dim) for r in results]
        return final_results[0] if is_single else final_results

    logger.info(f"Cache miss: computing {len(to_compute)} new embeddings...")

    # 2. Compute via chosen engine
    computed_vectors = []
    if settings.embedding_engine == "fastembed":
        model = get_fastembed_model()
        # FastEmbed is sync but fast, no need for async overhead here
        computed_vectors = list(model.embed(to_compute))
        # Convert ndarray to list
        computed_vectors = [v.tolist() for v in computed_vectors]
    else:
        # Gemini API
        client = get_gemini_client()
        if not client:
            raise ValueError("Gemini engine selected but API key is missing.")

        await AIRateLimiter.throttle(task_type="embedding")
        response = await client.aio.models.embed_content(
            model=model_name,
            contents=to_compute,
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )
        computed_vectors = [emb.values for emb in response.embeddings]

    # 3. Save results to cache
    async def _save_cache(db_conn):
        for idx, (original_idx, content_hash) in enumerate(compute_map):
            vector = computed_vectors[idx]
            results[original_idx] = vector
            await db_conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache
                (content_hash, vector, model_name)
                VALUES (?, ?, ?)
            """,
                (content_hash, json.dumps(vector), model_name),
            )
        await db_conn.commit()

    if conn:
        await _save_cache(conn)
    else:
        async with await async_get_connection() as db:
            await _save_cache(db)

    # Ensure all slots are filled
    dim = 384 if settings.embedding_engine == "fastembed" else 768
    final_results = [r if r is not None else ([0.0] * dim) for r in results]
    return final_results[0] if is_single else final_results


def _get_text_hash(text: str) -> str:
    """Returns SHA-256 hash of the text for robust caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
