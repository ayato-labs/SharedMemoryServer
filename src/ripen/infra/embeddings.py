import hashlib
from typing import Any

from ripen.common.config import settings
from ripen.common.utils import get_logger, normalize_text
from ripen.core.ai_control import AIRateLimiter, retry_on_ai_quota
from ripen.infra.database import retry_on_db_lock

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


async def check_embeddings_health() -> bool:
    """Checks if the configured embedding engine is ready."""
    try:
        if settings.embedding_engine == "fastembed":
            get_fastembed_model()
            return True
        else:
            return settings.api_key is not None
    except Exception as e:
        logger.debug(f"Embeddings health check failed: {e}")
        return False


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
    text_list: str | list[str], _conn: Any = None
) -> list[float] | list[list[float]]:
    """
    Computes text embeddings using the configured engine (FastEmbed or Gemini).
    """
    is_single = isinstance(text_list, str)
    items = [text_list] if is_single else text_list

    # 1. Normalize and filter
    valid_entries = [(i, clean) for i, raw in enumerate(items) if (clean := normalize_text(raw))]

    if not valid_entries:
        dim = 384 if settings.embedding_engine == "fastembed" else 768
        fallback = [([0.0] * dim) for _ in items]
        return fallback[0] if is_single else fallback

    logger.info(f"Computing embeddings for {len(items)} items using {settings.embedding_engine}...")
    results = [None] * len(items)
    to_compute = []
    compute_map = []
    model_name = settings.embedding_model

    from ripen.infra.uow import UnitOfWork

    async with UnitOfWork() as uow:
        # Check Cache
        for original_idx, txt in valid_entries:
            content_hash = _get_text_hash(txt)
            cached = await uow.embeddings.get_cached_embedding(content_hash, model_name)
            if cached:
                results[original_idx] = cached
            else:
                to_compute.append(txt)
                compute_map.append((original_idx, content_hash))

        if to_compute:
            logger.info(f"Cache miss: computing {len(to_compute)} new embeddings...")
            new_vectors = await _run_engine_computation(to_compute, model_name)
            for (idx, content_hash), vector in zip(compute_map, new_vectors, strict=True):
                results[idx] = vector
                await uow.embeddings.insert_cache_entry(content_hash, vector, model_name)

    # Fill safety fallbacks
    dim = 384 if settings.embedding_engine == "fastembed" else 768
    final_results = [r if r is not None else ([0.0] * dim) for r in results]
    return final_results[0] if is_single else final_results


async def _run_engine_computation(to_compute: list[str], model_name: str) -> list[list[float]]:
    """Internal helper to run the actual embedding engine."""
    if settings.embedding_engine == "fastembed":
        model = get_fastembed_model()
        return [v.tolist() for v in list(model.embed(to_compute))]

    client = get_gemini_client()
    if not client:
        raise ValueError("Gemini engine selected but API key is missing.")

    await AIRateLimiter.throttle(task_type="embedding")
    response = await client.aio.models.embed_content(
        model=model_name,
        contents=to_compute,
        config={"task_type": "RETRIEVAL_DOCUMENT"},
    )
    return [emb.values for emb in response.embeddings]


def _get_text_hash(text: str) -> str:
    """Returns SHA-256 hash of the text for robust caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
