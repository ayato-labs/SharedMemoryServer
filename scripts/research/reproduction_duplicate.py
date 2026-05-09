import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory.core.thought_logic import process_thought_core, init_thoughts_db, get_thought_history
from shared_memory.common.utils import get_thoughts_db_path

async def reproduce_duplicate_issue():
    print("--- Starting Reproduction: Sequential Thinking ID Duplicate ---")
    
    # Initialize DB (Robustly handles existing duplicates)
    await init_thoughts_db(force=True)
    
    session_id = f"repro_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 1. First thought
    print(f"Inserting thought #1 for session {session_id}...")
    await process_thought_core(
        thought="First thought",
        thought_number=1,
        total_thoughts=5,
        next_thought_needed=True,
        session_id=session_id
    )
    
    # 2. Duplicate thought (same number)
    print(f"Inserting DUPLICATE thought #1 for session {session_id}...")
    result = await process_thought_core(
        thought="Duplicate thought",
        thought_number=1,
        total_thoughts=5,
        next_thought_needed=True,
        session_id=session_id
    )
    
    if "error" in result:
        print(f"SUCCESS: Duplicate detected with error: {result['error']}")
    else:
        print("FAILURE: Duplicate was ALLOWED without error.")
    
    # 3. Verify history
    history = await get_thought_history(session_id)
    print(f"History length for {session_id}: {len(history)}")
    for i, t in enumerate(history):
        print(f"  [{i}] ID: {t['id']}, Num: {t['thought_number']}, Content: {t['thought']}")

    if len(history) > 1 and history[0]['thought_number'] == history[1]['thought_number']:
        print("!!! CONFIRMED: Database contains duplicate thought_numbers for the same session.")

if __name__ == "__main__":
    asyncio.run(reproduce_duplicate_issue())
