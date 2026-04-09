import asyncio
import os
import sys

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory.database import init_db

async def run_init():
    print("--- SharedMemoryServer DB Initialization ---")
    try:
        await init_db()
        print("[Success] All tables checked and initialized (including embedding_cache).")
    except Exception as e:
        print(f"[Error] Failed to initialize DB: {e}")

if __name__ == "__main__":
    asyncio.run(run_init())
