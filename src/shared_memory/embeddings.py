import hashlib
import json
import os
import sqlite3

from google import genai

from shared_memory.database import get_connection
from shared_memory.utils import log_error

EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONALITY = 768


def _get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_cached_embedding(text_hash: str) -> list[float] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT vector FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
            (text_hash, EMBEDDING_MODEL),
        ).fetchone()
        if row:
            return json.loads(row[0].decode("utf-8"))
    except sqlite3.Error as e:
        log_error("Failed to read from embedding cache", e)
    finally:
        conn.close()
    return None


def _save_to_cache(text_hash: str, vector: list[float]):
    conn = get_connection()
    try:
        vector_json = json.dumps(vector).encode("utf-8")
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache (content_hash, vector, model_name) VALUES (?, ?, ?)",
            (text_hash, vector_json, EMBEDDING_MODEL),
        )
        conn.commit()
    except sqlite3.Error as e:
        log_error("Failed to save to embedding cache", e)
    finally:
        conn.close()


def get_gemini_client() -> genai.Client | None:
    """
    Retrieves a Gemini API client using the best available API key.
    Prioritizes:
    1. Environment variables (GOOGLE_API_KEY or GEMINI_API_KEY)
    2. .env file
    3. Global settings.json (SharedMemoryServer specific env)
    4. Global settings.json (fallback)
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    # 2. Try loading from .env if still missing
    if not api_key:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        except ImportError:
            # python-dotenv is an optional dependency
            pass
        except Exception as e:
            log_error("Error loading .env file", e)

    # 3. Try loading from global settings.json
    if not api_key:
        home = os.path.expanduser("~")
        global_settings_path = os.path.join(home, ".gemini", "settings.json")
        if os.path.exists(global_settings_path):
            try:
                with open(global_settings_path, encoding="utf-8") as f:
                    settings = json.load(f)

                    # Targeted: settings.json -> mcpServers -> SharedMemoryServer -> env
                    mcp_env = (
                        settings.get("mcpServers", {})
                        .get("SharedMemoryServer", {})
                        .get("env", {})
                    )
                    api_key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get(
                        "GEMINI_API_KEY"
                    )

                    # Fallback: Top-level or any occurrence
                    if not api_key:
                        api_key = settings.get("GOOGLE_API_KEY") or settings.get(
                            "GEMINI_API_KEY"
                        )
            except Exception as e:
                log_error(f"Failed to read settings from {global_settings_path}", e)

    if not api_key:
        return None

    try:
        return genai.Client(api_key=api_key.strip())
    except Exception as e:
        log_error("Failed to initialize Gemini client", e)
        return None


async def compute_embedding(text: str) -> list[float] | None:
    """Computes embedding with local caching."""
    text_hash = _get_text_hash(text)
    cached = _get_cached_embedding(text_hash)
    if cached:
        return cached

    client = get_gemini_client()
    if not client:
        return None

    try:
        # Standard embedding request
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": DIMENSIONALITY},
        )
        vector = response.embeddings[0].values
        _save_to_cache(text_hash, vector)
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
        cached = _get_cached_embedding(text_hash)
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
        # Batch embedding request
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=to_compute,
            config={"output_dimensionality": DIMENSIONALITY},
        )
        for i, emb in enumerate(response.embeddings):
            vector = emb.values
            _save_to_cache(_get_text_hash(to_compute[i]), vector)
            results[indices[i]] = vector
    except Exception as e:
        log_error("Bulk embedding computation failed", e)

    return results
