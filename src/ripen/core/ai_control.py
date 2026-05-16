import asyncio
import random
import re
from functools import wraps
from typing import ClassVar

from loguru import logger


class ModelManager:
    """
    Manages Generative AI model rotation for fallback.
    Supports multiple pools (generation, compression).
    """

    def __init__(self):
        self._lock = None
        self._indices = {"generation": 0, "compression": 0}
        self._models = {}

    def _get_lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_pool(self, pool_name: str):
        if pool_name not in self._models:
            from ripen.common.config import GOOGLE_AI_MODELS, GOOGLE_COMPRESSION_MODELS

            if pool_name == "compression":
                self._models["compression"] = GOOGLE_COMPRESSION_MODELS
            else:
                self._models["generation"] = GOOGLE_AI_MODELS
        return self._models[pool_name]

    def get_current_model(self, pool_name: str = "generation") -> str:
        pool = self._get_pool(pool_name)
        idx = self._indices.get(pool_name, 0)
        return pool[idx]

    async def rotate(self, pool_name: str = "generation") -> bool:
        """
        Rotates to the next model in the specified pool.
        Returns True if we have completed a full cycle and are back at the start.
        """
        async with self._get_lock():
            pool = self._get_pool(pool_name)
            self._indices[pool_name] = (self._indices.get(pool_name, 0) + 1) % len(pool)
            is_full_cycle = self._indices[pool_name] == 0
            logger.info(
                f"Model pool '{pool_name}' rotated to: {self.get_current_model(pool_name)} "
                f"(Full cycle: {is_full_cycle})"
            )
            return is_full_cycle


# Singleton Model Manager
model_manager = ModelManager()


def parse_retry_delay(error: Exception) -> float | None:
    """
    Parses the retry delay from a Gemini API error.
    """
    error_str = str(error)
    match = re.search(r"retry in ([\d.]+)s", error_str)
    if match:
        return float(match.group(1))

    try:
        if hasattr(error, "message") and isinstance(error.message, dict):
            details = error.message.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                    delay_str = detail.get("retryDelay", "0s")
                    return float(delay_str.rstrip("s"))
    except Exception as e:
        logger.debug(f"Could not parse retry delay from error details: {e}")
    return None


def retry_on_ai_quota(
    max_retries: int = 5,
    initial_backoff: float = 1.0,
    rotate_models: bool = True,
    pool_name: str = "generation",
):
    """
    Decorator for retrying AI API calls on 429 RESOURCE_EXHAUSTED errors.
    Implements model fallback and exponential backoff.
    :param rotate_models: If True, switches models on 429. If False, just waits.
    :param pool_name: The model pool to rotate within.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None

            # total_attempts is the initial try plus max_retries,
            # multiplied by the number of models if rotation is enabled.
            models = model_manager._get_pool(pool_name)
            multiplier = len(models) if rotate_models else 1
            total_attempts = (max_retries + 1) * multiplier

            for attempt in range(total_attempts):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_error = e
                    e_str = str(e).upper()

                    if (
                        "429" in e_str
                        or "RESOURCE_EXHAUSTED" in e_str
                        or "500" in e_str
                        or "INTERNAL" in e_str
                        or "503" in e_str
                        or "SERVICE_UNAVAILABLE" in e_str
                    ):
                        wait_time = parse_retry_delay(e)

                        if rotate_models:
                            is_full_cycle = await model_manager.rotate(pool_name)
                            if is_full_cycle:
                                cycle_count = attempt // len(models)
                                wait_time = wait_time or (initial_backoff * (2**cycle_count))
                                logger.warning(
                                    f"All models in pool '{pool_name}' exhausted or errored. "
                                    f"Cycle {cycle_count + 1} complete. Waiting {wait_time:.2f}s "
                                    "before restarting..."
                                )
                                await asyncio.sleep(wait_time)
                            else:
                                logger.info(
                                    f"API error detected in pool '{pool_name}'. Falling back to "
                                    f"{model_manager.get_current_model(pool_name)}..."
                                )
                                await asyncio.sleep(random.uniform(0.1, 0.3))
                        else:
                            # Just exponential backoff without rotation
                            wait_time = wait_time or (initial_backoff * (2**attempt))
                            logger.warning(
                                f"API error or quota limit reached for pool '{pool_name}'. "
                                f"Attempt {attempt + 1}. Waiting {wait_time:.2f}s..."
                            )
                            await asyncio.sleep(wait_time)
                        continue
                    raise e
            raise last_error

        return wrapper

    return decorator


class AIRateLimiter:
    """
    Centralized rate limiter for AI API calls (Gemini).
    """

    _last_call_times: ClassVar[dict[str, float]] = {}
    _locks: ClassVar[dict[any, asyncio.Lock]] = {}

    GENERATION_INTERVAL = 1.0
    EMBEDDING_INTERVAL = 0.2

    @classmethod
    def set_min_interval(cls, interval: float, task_type: str = "generation"):
        """Sets the minimum interval between calls (for testing)."""
        if task_type == "generation":
            cls.GENERATION_INTERVAL = interval
        else:
            cls.EMBEDDING_INTERVAL = interval

    @classmethod
    async def throttle(cls, task_type: str = "generation"):
        interval = cls.GENERATION_INTERVAL if task_type == "generation" else cls.EMBEDDING_INTERVAL

        loop = asyncio.get_running_loop()
        lock_key = (task_type, loop)
        if lock_key not in cls._locks:
            cls._locks[lock_key] = asyncio.Lock()

        async with cls._locks[lock_key]:
            now = loop.time()
            last_time = cls._last_call_times.get(task_type, 0.0)
            elapsed = now - last_time

            if elapsed < interval:
                wait_time = interval - elapsed
                logger.debug(f"AI Quota Throttling ({task_type}): Waiting {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                cls._last_call_times[task_type] = asyncio.get_event_loop().time()
            else:
                cls._last_call_times[task_type] = now
