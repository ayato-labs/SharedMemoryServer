import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.abspath("src"))

from ripen.infra.uow import SecureWriteContext
from ripen.ops.lifecycle import run_knowledge_gc_logic
from ripen.domain.models import STALE_ACCESS_THRESHOLD

async def test_gc_logic():
    print("--- SoC Step 1: GC Logic Test ---")
    
    async with SecureWriteContext() as uow:
        # 1. Setup mock metadata (if needed, but we can just run it)
        # We'll do a dry run first
        print(f"Running GC logic (STALE_THRESHOLD={STALE_ACCESS_THRESHOLD})...")
        result = await run_knowledge_gc_logic(uow, age_days=0, dry_run=True)
        print(f"Dry Run Result: {result}")
        
        # 2. Check if the call to get_low_activity_ids succeeded
        # (If it didn't, it would have raised an error caught by the try-except in lifecycle.py)
        if "Error" in result:
            print(f"FAILED: {result}")
            return False
            
    print("PASSED: GC Logic successfully decoupled and executed.")
    return True

if __name__ == "__main__":
    asyncio.run(test_gc_logic())
