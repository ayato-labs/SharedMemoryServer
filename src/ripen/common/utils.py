import asyncio
import math
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from ripen.common.exceptions import SecurityError

_LOGGING_CONFIGURED = False


def get_resource_path(relative_path: str) -> Path:
    """
    Resolves resource paths relative to the 'ripen' package root.
    Works for both standard execution and PyInstaller 'frozen' state.
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller mode: resources are bundled under _MEIPASS/ripen
        base_path = Path(sys._MEIPASS) / "ripen"
    else:
        # Dev mode: resolve relative to src/ripen
        # utils.py is in src/ripen/common/utils.py
        base_path = Path(__file__).parent.parent

    return (base_path / relative_path).absolute()


def configure_logging():
    """
    Configures Loguru for structured JSON logging and traceability.
    - stderr: Human-readable colored output for development.
    - logs/server_{time}.jsonl: Structured JSON for traceability (retains last 2 runs).
    - logs/error.jsonl: Structured JSON quarantine for ERROR and CRITICAL levels.
    """
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    logger.remove()

    # 1. Stderr (Development / Human-readable)
    stderr_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level:7}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=stderr_format,
        level=os.environ.get("LOG_LEVEL", "DEBUG"),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    if hasattr(sys, "_MEIPASS"):
        # Production/Binary mode: Use app data directory for logs
        shared_home = os.environ.get("RIPEN_HOME") or os.environ.get("SHARED_MEMORY_HOME")
        if shared_home:
            log_dir = Path(shared_home).absolute() / "logs"
        else:
            log_dir = Path(os.path.expanduser("~")) / ".ripen" / "logs"
    else:
        # Development mode: Use project root (Ripen-free/logs)
        log_dir = Path(__file__).parents[3] / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # 2. Structured Error Log (Quarantine)
    # Only stores ERROR and higher, separate from main logs, JSON formatted
    logger.add(
        log_dir / "error.jsonl",
        level="ERROR",
        serialize=True,
        rotation="10 MB",
        retention="30 days",
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
        enqueue=True,
    )

    if "PYTEST_CURRENT_TEST" in os.environ:
        _LOGGING_CONFIGURED = True
        logger.info("Logging infrastructure initialized for TEST environment")
        return

    # 3. Main Structured JSON log (Traceability)
    # Keeping only last 2 executions via retention=2
    # Filename includes date/time to distinguish runs
    logger.add(
        log_dir / "server_{time:YYYY-MM-DD_HH-mm-ss}.jsonl",
        level="DEBUG",
        serialize=True,
        retention=2,
        encoding="utf-8",
        enqueue=True,
    )

    _LOGGING_CONFIGURED = True
    logger.info(f"Logging infrastructure initialized (Startup: {datetime.now().isoformat()})")


def get_logger(name: str):
    """
    Returns a loguru logger bound to a specific name.
    """
    return logger.bind(name=f"ripen.{name}")


def log_info(msg: str):
    """Abstraction for logging info messages."""
    logger.info(msg)


def log_error(msg: str, error: Exception | None = None):
    """Abstraction for logging error messages with optional exception details."""
    if error:
        # Use loguru's native formatting
        logger.opt(exception=error).error(msg)
    else:
        logger.error(msg)


def get_db_path() -> str:
    """Returns the absolute path to the knowledge database."""
    from ripen.common.config import settings

    return str(settings.db_path)


def get_thoughts_db_path() -> str:
    """Returns the absolute path to the thoughts database."""
    from ripen.common.config import settings

    return str(settings.thoughts_db_path)


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


def normalize_text(text: str, truncate: int = 10000) -> str:
    """
    Standardizes text for storage and AI processing.
    - Strips leading/trailing whitespace.
    - Compresses multiple spaces/newlines into single ones.
    - Limits length to prevent token overflow.
    """
    if not text:
        return ""
    # Normalize whitespace: replace any whitespace sequence with a single space
    normalized = re.sub(r"\s+", " ", text).strip()
    logger.debug(f"Normalized text: {len(text)} -> {len(normalized)} chars")
    return normalized[:truncate] if truncate > 0 else normalized


def clean_markdown(text: str) -> str:
    """
    Strips dangerous or unnecessary markdown elements from distilled content.
    """
    if not text:
        return ""
    # Simple regex to strip code blocks backticks if they wrap the whole thing
    cleaned = re.sub(r"^```markdown\n", "", text)
    cleaned = re.sub(r"\n```$", "", cleaned)
    logger.debug(f"Cleaned markdown: {len(text)} -> {len(cleaned)} chars")
    return cleaned.strip()


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


def escape_fts5_query(query: str) -> str:
    """
    Escapes a string for use in an SQLite FTS5 MATCH clause.
    - Replaces internal double quotes with two double quotes.
    - Wraps each word in double quotes to allow safe "AND" search.
    - Returns an empty string if the query is empty or contains no valid parts.
    """
    if not query:
        return ""

    # Split by whitespace
    parts = query.split()
    if not parts:
        return ""

    escaped_parts = []
    for p in parts:
        # FTS5 uses double quotes for phrase queries.
        # To include a literal double quote, it must be doubled.
        p_esc = p.replace('"', '""')
        escaped_parts.append(f'"{p_esc}"')

    return " ".join(escaped_parts)


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

        score = freq_score * decay
        logger.debug(
            f"Importance: {score:.4f} (freq={freq_score:.2f}, "
            f"decay={decay:.2f}, days={days_ago:.1f})"
        )
        return score
    except Exception as e:
        logger.error(
            f"Importance calculation failed for count={access_count}, last={last_accessed}: {e}"
        )
        return 0.0


def safe_main_executor(main_func):
    """
    Executes a main function with error handling and a terminal pause.
    Prevents the terminal window from closing immediately on error or exit.
    """

    def wrapper(*args, **kwargs):
        configure_logging()
        try:
            return main_func(*args, **kwargs)
        except Exception as e:
            logger.exception("FATAL ERROR: Application crashed.")
            # Ensure the terminal doesn't close abruptly ONLY if it's a TTY
            # Background MCP services must exit to avoid deadlocks
            if sys.stdin.isatty():
                logger.critical("!" * 60)
                logger.critical("  FATAL ERROR OCCURRED")
                logger.critical(f"  {type(e).__name__}: {e}")
                logger.critical("  Check logs/error.log for full traceback.")
                logger.critical("!" * 60)
                try:
                    input("\nPress [Enter] to close the terminal...")
                except (EOFError, KeyboardInterrupt):
                    pass
            sys.exit(1)
        except KeyboardInterrupt:
            # Usually we don't want to pause on Ctrl+C, just exit quietly
            sys.exit(0)

    return wrapper
