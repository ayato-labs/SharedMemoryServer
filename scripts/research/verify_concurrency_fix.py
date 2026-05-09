
import asyncio
import time
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from shared_memory.core.thought_logic import process_thought_core, init_thoughts_db
from shared_memory.infra.database import init_db

async def simulate_concurrent_thoughts():
    session_id = f"test_concurrency_{int(time.time())}"
    print(f"Starting concurrency test for session: {session_id}")
    
    await init_db()
    await init_thoughts_db()

    # We want to call process_thought_core concurrently.
    # In a real race, Thought 1 and Thought 2 might arrive almost at the same time.
    
    async def call_thought(number, delay=0):
        if delay:
            await asyncio.sleep(delay)
        print(f"Calling Thought #{number}...")
        start = time.perf_counter()
        result = await process_thought_core(
            thought=f"This is thought number {number}",
            thought_number=number,
            total_thoughts=10,
            next_thought_needed=True,
            session_id=session_id
        )
        duration = time.perf_counter() - start
        print(f"Thought #{number} finished in {duration:.3f}s. History length: {result.get('thoughtHistoryLength')}")
        return result

    # Launch Thought 1 and Thought 2 almost simultaneously
    # With the lock, Thought 2 should wait for Thought 1 to finish.
    tasks = [
        call_thought(1),
        call_thought(2, delay=0.1) # Slightly delayed but should overlap if no lock
    ]
    
    results = await asyncio.gather(*tasks)
    
    print("\nVerification:")
    # Check if Thought 2 saw the history from Thought 1
    # If Thought 2 finished after Thought 1 and they were serialized, 
    # Thought 2 should see history length = 2.
    # Note: process_thought_core returns history_length AFTER insert.
    
    t1_history = results[0]['thoughtHistoryLength']
    t2_history = results[1]['thoughtHistoryLength']
    
    print(f"T1 history length: {t1_history}")
    print(f"T2 history length: {t2_history}")
    
    if t2_history == 2:
        print("SUCCESS: Thought 2 correctly followed Thought 1 (Serialized).")
    else:
        print("FAILURE: Race condition detected or serialization failed.")

if __name__ == "__main__":
    asyncio.run(simulate_concurrent_thoughts())
