import asyncio
import math
import os
import re
from datetime import UTC, datetime

from loguru import logger

from shared_memory.exceptions import SecurityError

# Global flag for structured logging (defined in config)
_STRUCTURED_LOGGING = False


def set_structured_logging(enabled: bool):
    global _STRUCTURED_LOGGING
    _STRUCTURED_LOGGING = enabled


def get_logger(name: str):
    """
    Returns a loguru logger bound to a specific name.
    """
    return logger.bind(name=f"shared_memory.{name}")


def log_info(msg: str):
    """Abstraction for logging info messages."""
    logger.info(msg)


def log_error(msg: str, error: Exception | None = None):
    """Abstraction for logging error messages with optional exception details."""
    if error:
        logger.exception(f"{msg}: {error}")
    else:
        logger.error(msg)


def get_db_path() -> str:
    """
    Returns the absolute path to the knowledge database.
    Prioritizes MEMORY_DB_PATH env var, then SHARED_MEMORY_HOME.
    """
    db_path = os.environ.get("MEMORY_DB_PATH")
    if db_path:
        return os.path.abspath(db_path)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "knowledge.db"))


def get_thoughts_db_path() -> str:
    """Returns the absolute path to the thoughts database."""
    db_path = os.environ.get("THOUGHTS_DB_PATH")
    if db_path:
        return os.path.abspath(db_path)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "thoughts.db"))


def get_bank_dir() -> str:
    """Returns the absolute path to the memory bank directory."""
    bank_dir = os.environ.get("MEMORY_BANK_DIR")
    if bank_dir:
        return os.path.abspath(bank_dir)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "bank"))


def calculate_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Calculates cosine similarity between two vectors.
    Returns 0.0 if vectors are empty or have different lengths.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(a * a for a in v2))

    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


def batch_cosine_similarity(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
    """
    Computes cosine similarity between a query vector and a list of vectors.
    """
    return [calculate_similarity(query_vector, v) for v in vectors]


def security_scan(content: str):
    """
    Placeholder for basic security scanning of content.
    Prevents potential prompt injection or malformed data issues.
    """
    if not content:
        return

    # Advanced security logic would go here
    # For now, we just ensure it's a string
    if not isinstance(content, str):
        raise SecurityError("Non-string content detected in security scan.")


def clean_markdown(text: str) -> str:
    """
    Strips dangerous or unnecessary markdown elements from distilled content.
    """
    if not text:
        return ""
    # Simple regex to strip code blocks backticks if they wrap the whole thing
    text = re.sub(r"^```markdown\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


class PathResolver:
    """Utility to resolve standard data paths."""

    @staticmethod
    def get_base_data_dir() -> str:
        home = os.environ.get("SHARED_MEMORY_HOME")
        if home:
            return os.path.abspath(home)
        return os.path.abspath("data")


# Intra-process Global Locks
_GLOBAL_LOCKS: dict[str, asyncio.Lock] = {}


class GlobalLock:
    """
    Provides a named, intra-process lock (asyncio.Lock).
    Used to prevent race conditions during file or database access
    within the same event loop.
    """

    def __init__(self, name: str):
        self.name = name
        if name not in _GLOBAL_LOCKS:
            _GLOBAL_LOCKS[name] = asyncio.Lock()
        self._lock = _GLOBAL_LOCKS[name]

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

    @property
    def file_locked(self) -> bool:
        return self._lock.locked()


def sanitize_filename(name: str) -> str:
    """
    Converts a string into a safe filename.
    Removes path traversal attempts and special characters.
    """
    # 0. Strip directories and spaces
    name = os.path.basename(name).strip()

    # 1. Strip ANY existing extension (e.g., .txt, .md) to enforce .md
    name, _ = os.path.splitext(name)
    name = name.strip()

    # 2. Replace anything not alphanumeric or underscore/hyphen/dot
    clean = re.sub(r"[^\w\-\.]", "_", name.lower())
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean)

    # 3. Prevent hidden files or path traversal
    clean = clean.lstrip(".")
    if not clean:
        clean = "unnamed_entity"

    return f"{clean}.md"


def mask_sensitive_data(text: str) -> str:
    """
    Masks sensitive information like API keys in logs or content.
    Identifies patterns like 'AIza...' (Google API keys) and 'sk-...' (Generic keys).
    """
    if not text:
        return ""
    # Mask Google API Key pattern
    text = re.sub(r"AIzaSy[a-zA-Z0-9\-_]{33}", "[GOOGLE_API_KEY_MASKED]", text)
    # Mask Generic/OpenAI API Key pattern
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[API_KEY_MASKED]", text)
    # Mask Email addresses
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_MASKED]", text)
    return text


def safe_path_join(base_dir: str, filename: str) -> str:
    """
    Safely joins a base directory with a filename, ensuring
    the resulting path is within the base directory.
    Prevents path traversal attacks.
    """
    base_dir = os.path.abspath(base_dir)
    filename = os.path.basename(filename)  # Only keep the last part
    joined = os.path.abspath(os.path.join(base_dir, filename))

    if not joined.startswith(base_dir):
        raise ValueError(f"Dangerous path detected: {joined}")

    return joined


def calculate_importance(access_count: int, last_accessed: str) -> float:
    """
    Calculates the importance score of a piece of knowledge based on
    access frequency and recency (time decay).
    """
    try:
        # 1. Base score from frequency (logarithmic scaling)
        freq_score = math.log1p(access_count)

        # 2. Time decay (Exponential decay)
        # Assuming last_accessed is an ISO timestamp
        last_dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        days_ago = (now - last_dt).total_seconds() / (24 * 3600)

        # Decay constant: half-life of 30 days
        decay = math.exp(-days_ago / 30.0)

        return freq_score * decay
    except Exception as e:
        log_error(
            f"Importance calculation failed for count={access_count}, last={last_accessed}", e
        )
        return 0.0





