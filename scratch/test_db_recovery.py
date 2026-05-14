import asyncio
import os
import sys

# Add src to sys.path
sys.path.append(os.path.abspath("src"))

from ripen.infra.database import init_db
from ripen.common.utils import get_db_path

async def test_recovery():
    db_path = get_db_path()
    print(f"Testing recovery for DB at: {db_path}")
    try:
        await init_db()
        print("Initialization complete!")
    except Exception as e:
        print(f"Initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_recovery())
