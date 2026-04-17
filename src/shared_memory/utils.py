import asyncio
import logging
import math
import os
import re
import shutil
import sys
import time
from datetime import UTC, datetime
from typing import Any

from shared_memory.exceptions import SecurityError

# Global flag for structured logging
ENABLE_STRUCTURED_LOGGING = (
    os.environ.get("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"
)


# Basic configuration for standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance for the given name.
    """
    return logging.getLogger(f"shared_memory.{name}")


def log_error(msg: str, e: Exception = None, extra: dict[str, Any] = None):
    """
    Standard error logger using logging module.
    """
    logger = get_logger("core")
    if e:
        logger.error(f"{msg}: {e}", extra=extra)
    else:
        logger.error(msg, extra=extra)


def log_info(msg: str, extra: dict[str, Any] = None):
    """
    Standard info logger using logging module.
    """
    logger = get_logger("core")
    logger.info(msg, extra=extra)


class PathResolver:
    """
    Autonomous path resolver for project-based context isolation.
    """

    @staticmethod
    def find_project_root() -> str:
        """
        Searches upwards from the current working directory for project indicators.
        Returns the home directory if no project root is found.
        """
        curr = os.getcwd()
        indicators = [
            ".git",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            ".clinerules",
            ".cursorrules",
        ]
        while curr != os.path.dirname(curr):
            if any(os.path.exists(os.path.join(curr, ind)) for ind in indicators):
                return curr
            curr = os.path.dirname(curr)
        return os.path.expanduser("~")

    @staticmethod
    def ensure_gitignore(root_dir: str):
        """
        Safely adds .shared_memory/ to .gitignore if it exists and doesn't
        already have it.
        """
        gitignore_path = os.path.join(root_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    content = f.read()
                if ".shared_memory/" not in content:
                    # Append with a clear comment
                    with open(gitignore_path, "a", encoding="utf-8") as f:
                        f.write("\n# SharedMemoryServer local data\n.shared_memory/\n")
                    log_info(f"Automatically added .shared_memory/ to {gitignore_path}")
            except Exception as e:
                log_error(f"Failed to update {gitignore_path}", e)

    @classmethod
    def get_base_data_dir(cls) -> str:
        """
        Determines the base directory for all SharedMemoryServer data.
        Implements auto-detection and legacy migration.
        """
        # 1. Environment Override (Power User / Explicit Path)
        env_dir = os.environ.get("SHARED_MEMORY_HOME")
        if env_dir:
            os.makedirs(env_dir, exist_ok=True)
            return env_dir

        # 2. Project Detection
        root = cls.find_project_root()
        data_dir = os.path.join(root, ".shared_memory")

        # 3. Initialization and Security
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                # If we found a real project (not just home), ensure security
                if root != os.path.expanduser("~"):
                    cls.ensure_gitignore(root)

                # 4. Migration Check (only on first creation)
                cls._migrate_legacy_data(root, data_dir)
            except Exception as e:
                log_error(f"Failed to initialize data directory {data_dir}", e)
                # Fallback to local if creation fails
                return os.getcwd()

        return data_dir

    @staticmethod
    def _migrate_legacy_data(root: str, new_dir: str):
        """
        Moves legacy data files/dirs from root to the new .shared_memory directory.
        """
        legacy_map = {
            "thoughts.db": "thoughts.db",
            "memory-bank": "bank",
        }
        migrated_any = False
        for old_name, new_name in legacy_map.items():
            old_path = os.path.join(root, old_name)
            new_path = os.path.join(new_dir, new_name)

            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    shutil.move(old_path, new_path)
                    log_info(
                        f"Migrated legacy data: {old_name} -> .shared_memory/{new_name}"
                    )
                    migrated_any = True
                except Exception as e:
                    log_error(f"Migration failed for {old_name}", e)

        if migrated_any:
            log_info("SharedMemoryServer legacy data migration completed.")


def get_db_path():
    """
    Returns the path to the SQLite knowledge database.
    Priority: MEMORY_DB_PATH env > PathResolver.
    """
    env_val = os.environ.get("MEMORY_DB_PATH")
    if env_val:
        return env_val
    return os.path.join(PathResolver.get_base_data_dir(), "knowledge.db")


def get_thoughts_db_path():
    """
    Returns the path to the thoughts/sequential thinking database.
    Priority: THOUGHTS_DB_PATH env > PathResolver.
    """
    env_val = os.environ.get("THOUGHTS_DB_PATH")
    if env_val:
        return env_val
    return os.path.join(PathResolver.get_base_data_dir(), "thoughts.db")


def get_bank_dir():
    """
    Returns the path to the Markdown memory bank directory.
    Priority: MEMORY_BANK_DIR env > PathResolver.
    """
    env_val = os.environ.get("MEMORY_BANK_DIR")
    if env_val:
        return env_val
    return os.path.join(PathResolver.get_base_data_dir(), "bank")


def mask_sensitive_data(text: str) -> str:
    if not isinstance(text, str):
        return text

    patterns = [
        (r"AIza[0-9A-Za-z-_]{35}", "[GOOGLE_API_KEY_MASKED]"),
        (r"sk-[a-zA-Z0-9\-]{20,}", "[API_KEY_MASKED]"),
        (r"(password\s*[:=]\s*)([^\s]+)", r"\1[PASSWORD_MASKED]"),
        (
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?"
            r"-----END [A-Z ]+ PRIVATE KEY-----",
            "[PRIVATE_KEY_MASKED]",
        ),
    ]

    masked_text = text
    for pattern, replacement in patterns:
        masked_text = re.sub(
            pattern,
            replacement,
            masked_text,
            flags=re.IGNORECASE if "password" in pattern else 0,
        )

    return masked_text


def sanitize_filename(filename: str) -> str:
    """
    Expert-level filename sanitization to prevent path traversal and
    illegal characters on any OS.
    """
    if not filename:
        return "unnamed_file.md"

    # Remove any directory components
    name = os.path.basename(filename)

    # Remove non-alphanumeric/dot/underscore/hyphen
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)

    # Force .md extension if missing or incorrect
    if not name.endswith(".md"):
        name = re.sub(r"\.[^.]+$", "", name)  # remove old extension
        name += ".md"

    return name


def safe_path_join(base_dir: str, filename: str) -> str:
    """
    Strict path joining that ensures the resulting path is within the base_dir.
    """
    sanitized = sanitize_filename(filename)
    full_path = os.path.normpath(os.path.join(base_dir, sanitized))

    if not full_path.startswith(os.path.normpath(base_dir)):
        raise SecurityError(f"Path traversal detected: {filename}")

    return full_path


class GlobalLock:
    """
    Expert-level cross-process locking using a lockfile.
    Placed in the project data directory to avoid pollution.
    """

    # Intra-process lock cache to minimize file system contention
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, lock_name: str, timeout: float = 30.0):
        self.lock_name = lock_name
        self.lock_path = os.path.join(
            PathResolver.get_base_data_dir(), f"{lock_name}.lock"
        )
        self.timeout = timeout
        self.file_locked = False
        self.intra_lock = None

    async def __aenter__(self):
        # 1. Acquire intra-process lock first
        if self.lock_name not in self._locks:
            self._locks[self.lock_name] = asyncio.Lock()
        self.intra_lock = self._locks[self.lock_name]

        # We wait for the intra-process lock indefinitely since it's in-memory and fast
        await self.intra_lock.acquire()

        # 2. Acquire cross-process file lock
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # Exclusive creation - atomic at OS level
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode())
                finally:
                    os.close(fd)
                self.file_locked = True
                return self
            except FileExistsError:
                # Check for stale lock (older than 10s)
                try:
                    mtime = os.path.getmtime(self.lock_path)
                    if time.time() - mtime > 10:
                        os.remove(self.lock_path)
                        log_info(f"Removed stale lock file: {self.lock_path}")
                except FileNotFoundError:
                    # Stale lock was already removed by another process, which is fine.
                    log_info(
                        f"Stale lock {self.lock_path} was "
                        "already removed by another process."
                    )
                except Exception as e:
                    log_error(f"Failed to remove stale lock {self.lock_path}", e)
                await asyncio.sleep(0.1)

        # Cleanup intra-lock if file lock fails
        self.intra_lock.release()
        raise TimeoutError(f"Could not acquire global lock for {self.lock_path}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.file_locked:
                for _ in range(5):
                    try:
                        if os.path.exists(self.lock_path):
                            os.remove(self.lock_path)
                        break
                    except PermissionError:
                        await asyncio.sleep(0.05)
                    except FileNotFoundError:
                        break
                self.file_locked = False
        finally:
            if self.intra_lock and self.intra_lock.locked():
                self.intra_lock.release()


def batch_cosine_similarity(
    query_vector: list[float], vectors: list[list[float]]
) -> list[float]:
    """
    Expert-level optimized batch cosine similarity.
    """
    if not vectors:
        return []

    # Pre-calculate query magnitude
    q_mag = math.sqrt(sum(v * v for v in query_vector))
    if q_mag == 0:
        return [0.0] * len(vectors)

    similarities = []
    for v in vectors:
        dot_product = sum(a * b for a, b in zip(query_vector, v, strict=False))
        v_mag = math.sqrt(sum(x * x for x in v))
        if v_mag == 0:
            similarities.append(0.0)
        else:
            similarities.append(dot_product / (q_mag * v_mag))
    return similarities


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Expert-level single cosine similarity.
    """
    if not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def calculate_importance(access_count: int, last_accessed_iso: str) -> float:
    """
    Calculates a weight based on access frequency and recency.
    """
    # 1. Frequency score (logarithmic to prevent saturation)
    freq_score = math.log1p(access_count) / 10.0  # Normalized roughly

    # 2. Recency score (Exponential decay)
    try:
        last_accessed = datetime.fromisoformat(last_accessed_iso)
        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(tzinfo=UTC)

        seconds_since = (datetime.now(UTC) - last_accessed).total_seconds()
        # Decay half-life: 24 hours (86400 seconds)
        recency_score = math.exp(-seconds_since / 86400.0)
    except Exception as e:
        log_error(f"Failed to calculate recency score for {last_accessed_iso}", e)
        recency_score = 0.5

    return (freq_score * 0.4) + (recency_score * 0.6)
