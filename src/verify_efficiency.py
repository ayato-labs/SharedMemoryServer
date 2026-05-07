import asyncio
import os
import json
from shared_memory.api.server import ensure_initialized
from shared_memory.core.logic import save_memory_core
from shared_memory.infra.database import close_all_connections

async def verify_efficiency():
    print("Initializing system for verification...")
    await ensure_initialized()
    
    test_content = "This is a highly repetitive piece of knowledge that should be cached correctly."
    entities = [{"name": "EfficiencyTest", "description": test_content}]
    
    print("\nStep 1: Saving memory for the first time (Cache Miss expected)...")
    res1 = await save_memory_core(entities=entities, agent_id="test_user")
    print(f"Result 1: {res1}")
    
    print("\nStep 2: Saving identical memory (Cache Hit expected)...")
    # Content with slightly different whitespace to test normalization
    test_content_noisy = "  This is a highly repetitive piece of knowledge   that should be cached correctly.  \n"
    entities_noisy = [{"name": "EfficiencyTest", "description": test_content_noisy}]
    
    res2 = await save_memory_core(entities=entities_noisy, agent_id="test_user")
    print(f"Result 2: {res2}")
    
    print("\nStep 3: Checking logs for 'CACHE (SHA-256)'...")
    log_file = "logs/server.jsonl"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            hits = [line for line in lines if "CACHE (SHA-256)" in line]
            if hits:
                print(f"SUCCESS: Found {len(hits)} cache hit(s) in logs.")
            else:
                print("FAILURE: No cache hits found in logs. Check normalization/hashing.")
    else:
        print("Log file not found. Verification partially skipped.")

    await close_all_connections()

if __name__ == "__main__":
    # Ensure we use a test DB
    os.environ["MEMORY_DB_PATH"] = "data/test_efficiency.db"
    if os.path.exists("data/test_efficiency.db"):
        os.remove("data/test_efficiency.db")
    
    asyncio.run(verify_efficiency())
