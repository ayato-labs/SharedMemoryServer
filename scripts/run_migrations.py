
import asyncio
import sys
import os

# Ensure the parent directory is in the path so we can import shared_memory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.migrations.manager import MigrationManager
from shared_memory.database import async_get_connection

async def main():
    print("--- SharedMemoryServer Migration Tool ---")
    mgr = MigrationManager()
    
    async with await async_get_connection() as conn:
        try:
            await mgr.run_migrations(conn)
            print("Migration process finished successfully.")
        except Exception as e:
            print(f"Migration process failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
