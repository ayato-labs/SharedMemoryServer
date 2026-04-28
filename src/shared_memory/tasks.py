import asyncio
from typing import Any, Callable, Coroutine
from loguru import logger

# Global set of background tasks to ensure graceful shutdown and prevent handle leaks
_BACKGROUND_TASKS: set[asyncio.Task] = set()

def create_background_task(
    coro: Coroutine[Any, Any, Any], 
    name: str | None = None,
    on_error: Callable[[Exception], None] | None = None
) -> asyncio.Task:
    """
    Creates and tracks a background task.
    """
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    
    def _done_callback(t: asyncio.Task):
        _BACKGROUND_TASKS.discard(t)
        try:
            if not t.cancelled() and t.exception():
                exc = t.exception()
                if on_error:
                    on_error(exc)
                else:
                    logger.error(f"Background task '{name or t.get_name()}' failed: {exc}", exc_info=True)
        except (asyncio.CancelledError, asyncio.InvalidStateError):
            pass

    task.add_done_callback(_done_callback)
    return task

async def wait_for_background_tasks(timeout: float = 5.0):
    """
    Wait for all currently tracked background tasks to complete.
    """
    if _BACKGROUND_TASKS:
        count = len(_BACKGROUND_TASKS)
        logger.info(f"Waiting for {count} background tasks to finish...")
        done, pending = await asyncio.wait(list(_BACKGROUND_TASKS), timeout=timeout)
        if pending:
            logger.warning(f"Timed out waiting for {len(pending)} background tasks.")
        else:
            logger.info("All background tasks completed.")
