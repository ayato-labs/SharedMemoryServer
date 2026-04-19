import asyncio
import os

import aiosqlite


async def check_schema():
    db_path = "shared_memory.db"
    if not os.path.exists(db_path):
        print("Database not found")
        return

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        print("--- Tables ---")
        async with conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'") as cursor:
            async for row in cursor:
                print(f"Table: {row['name']}")
                print(f"SQL: {row['sql']}\n")

        print("--- Indexes ---")
        async with conn.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'"
        ) as cursor:
            async for row in cursor:
                print(f"Index: {row['name']} on {row['tbl_name']}")
                print(f"SQL: {row['sql']}\n")


if __name__ == "__main__":
    asyncio.run(check_schema())
