import asyncio
import time
import sys
import os
from pathlib import Path

# Add src to sys.path
sys.path.append(os.path.abspath("src"))

from ripen.common.utils import configure_logging, get_logger
from ripen.common.config import settings

# Initialize logging to see what happens
configure_logging()
logger = get_logger("unit_test_unmocked")

async def test_fastembed_initialization():
    """Unit test for FastEmbed (Unmocked)."""
    logger.info("TEST: Starting FastEmbed initialization (Unmocked)...")
    start = time.perf_counter()
    try:
        from ripen.infra.embeddings import get_fastembed_model
        # This will trigger the actual download/loading of the model
        model = get_fastembed_model()
        elapsed = time.perf_counter() - start
        logger.info(f"SUCCESS: FastEmbed initialized in {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.error(f"FAILED: FastEmbed initialization failed: {e}")
        return False

async def test_llm_health_check():
    """Unit test for LLM Provider (Unmocked)."""
    logger.info(f"TEST: Starting LLM health check for provider: {settings.llm_provider} (Unmocked)...")
    start = time.perf_counter()
    try:
        from ripen.infra.llm import get_llm_provider
        provider = get_llm_provider()
        # This makes a REAL network call to Ollama or Gemini
        is_ok = await provider.check_health()
        elapsed = time.perf_counter() - start
        if is_ok:
            logger.info(f"SUCCESS: LLM health check passed in {elapsed:.2f}s")
        else:
            logger.warning(f"WARNING: LLM health check returned OFFLINE (but didn't crash) in {elapsed:.2f}s")
        return is_ok
    except Exception as e:
        logger.error(f"FAILED: LLM health check failed with exception: {e}")
        return False

async def test_db_init_hard():
    """Unit test for DB initialization with heavy check."""
    logger.info("TEST: Starting hard DB initialization check...")
    from ripen.infra.database import init_db
    try:
        # Force re-init
        await init_db(force=True)
        logger.info("SUCCESS: DB initialization complete.")
        return True
    except Exception as e:
        logger.error(f"FAILED: DB initialization failed: {e}")
        return False

async def run_all():
    logger.info("=== STARTING UNMOCKED UNIT TESTS ===")
    
    # We run them one by one to isolate the hang
    results = {}
    
    # 1. DB (Usually fast)
    results["DB_INIT"] = await test_db_init_hard()
    
    # 2. FastEmbed (Potential hang point)
    # Use a timeout to detect hang
    try:
        results["FASTEMBED"] = await asyncio.wait_for(test_fastembed_initialization(), timeout=60.0)
    except asyncio.TimeoutError:
        logger.error("CRITICAL HANG: FastEmbed initialization timed out after 60s!")
        results["FASTEMBED"] = "TIMEOUT"
    
    # 3. LLM (Potential network delay)
    try:
        results["LLM"] = await asyncio.wait_for(test_llm_health_check(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("CRITICAL HANG: LLM health check timed out after 30s!")
        results["LLM"] = "TIMEOUT"

    logger.info("=== TEST RESULTS ===")
    for k, v in results.items():
        logger.info(f"{k}: {v}")

if __name__ == "__main__":
    asyncio.run(run_all())
