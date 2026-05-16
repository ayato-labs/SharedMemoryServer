
import asyncio
import logging
import sys
import time
from ripen.core.logic import read_memory_core

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger("logic_test")

async def test_logic_directly():
    query = "test query"
    logger.info(f"DIRECT LOGIC TEST: Calling read_memory_core with query='{query}'")
    
    start = time.perf_counter()
    try:
        # We call the core logic directly, bypassing MCP/SSE/Proxy
        result = await read_memory_core(query)
        duration = time.perf_counter() - start
        logger.info(f"SUCCESS: Result received in {duration:.2f}s")
        logger.info(f"RESULT: {str(result)[:500]}...")
    except Exception as e:
        logger.error(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_logic_directly())
