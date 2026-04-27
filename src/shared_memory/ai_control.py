import asyncio
import random
import re
from functools import wraps

from loguru import logger

class ModelManager:
    """
    Manages Generative AI model rotation for fallback.
    LLM only. NEVER rotate embedding models.
    """
    def __init__(self):
        self._lock = asyncio.Lock()
        self.current_index = 0
        self._models = None

    @property
    def models(self):
        if self._models is None:
            from shared_memory.config import GOOGLE_AI_MODELS
            self._models = GOOGLE_AI_MODELS
        return self._models

    def get_current_model(self) -> str:
        return self.models[self.current_index]

    async def rotate(self) -> bool:
        """
        Rotates to the next model. 
        Returns True if we have completed a full cycle and are back at the start.
        """
        async with self._lock:
            self.current_index = (self.current_index + 1) % len(self.models)
            is_full_cycle = (self.current_index == 0)
            logger.info(f"Model rotated to: {self.get_current_model()} (Full cycle: {is_full_cycle})")
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
    except Exception:
        pass
    return None


def retry_on_ai_quota(max_retries: int = 5, initial_backoff: float = 1.0):
    """
    Decorator for retrying AI API calls on 429 RESOURCE_EXHAUSTED errors.
    Implements model fallback and exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            # Each 'attempt' tries to use a model.
            # We try up to max_retries full cycles if needed.
            total_attempts = max_retries * len(model_manager.models)
            
            for attempt in range(total_attempts):
                try:
                    # The decorated function might use settings.generative_model
                    # which we will update to point to model_manager.get_current_model().
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    last_error = e
                    e_str = str(e).upper()
                    
                    if "429" in e_str or "RESOURCE_EXHAUSTED" in e_str:
                        is_full_cycle = await model_manager.rotate()
                        
                        if is_full_cycle:
                            # Exponential backoff on full cycle
                            cycle_count = attempt // len(model_manager.models)
                            wait_time = parse_retry_delay(e) or (initial_backoff * (2 ** cycle_count))
                            logger.warning(
                                f"All models exhausted (429). Cycle {cycle_count+1} complete. "
                                f"Waiting {wait_time:.2f}s before restarting..."
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            # Fallback immediately
                            logger.info(
                                f"Model 429 detected. Falling back to {model_manager.get_current_model()}..."
                            )
                            await asyncio.sleep(random.uniform(0.1, 0.3))
                        continue
                    raise e
            raise last_error
        return wrapper
    return decorator


class AIRateLimiter:
    """
    Centralized rate limiter for AI API calls (Gemini).
    """
    _last_call_times: dict[str, float] = {}
    _locks: dict[str, asyncio.Lock] = {}

    GENERATION_INTERVAL = 6.0
    EMBEDDING_INTERVAL = 1.0

    @classmethod
    async def throttle(cls, task_type: str = "generation"):
        interval = (
            cls.GENERATION_INTERVAL if task_type == "generation" else cls.EMBEDDING_INTERVAL
        )

        if task_type not in cls._locks:
            cls._locks[task_type] = asyncio.Lock()

        async with cls._locks[task_type]:
            now = asyncio.get_event_loop().time()
            last_time = cls._last_call_times.get(task_type, 0.0)
            elapsed = now - last_time

            if elapsed < interval:
                wait_time = interval - elapsed
                logger.debug(f"AI Quota Throttling ({task_type}): Waiting {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                cls._last_call_times[task_type] = asyncio.get_event_loop().time()
            else:
                cls._last_call_times[task_type] = now
