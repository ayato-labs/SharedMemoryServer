import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory.utils import get_db_path, get_thoughts_db_path
import aiosqlite

async def inspect_db():
    db_path = get_db_path()
    t_db_path = get_thoughts_db_path()
    
    print(f"DEBUG: Knowledge DB Path: {db_path}")
    print(f"DEBUG: Thoughts DB Path:  {t_db_path}")

    async def list_tables(path):
        if not os.path.exists(path):
            return "File NOT found"
        async with aiosqlite.connect(path) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in await cursor.fetchall()]
            return ", ".join(tables) if tables else "No tables"

    print(f"Knowledge Tables: {await list_tables(db_path)}")
    print(f"Thoughts Tables:  {await list_tables(t_db_path)}")

if __name__ == "__main__":
    asyncio.run(inspect_db())
