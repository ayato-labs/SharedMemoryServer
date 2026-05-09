import asyncio
import os
import sys

# Ensure the parent directory is in the path so we can import ripen
# This is useful when running this script directly from the scripts folder.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ripen.database import async_get_connection
from ripen.migrations.manager import MigrationManager


async def run_standalone():
    """CLI entry point for manual migration run."""
    print("--- Ripen Manual Migration Tool ---")
    mgr = MigrationManager()
    async with await async_get_connection() as conn:
        await mgr.run_migrations(conn)
    print("Migration check complete.")


if __name__ == "__main__":
    asyncio.run(run_standalone())
