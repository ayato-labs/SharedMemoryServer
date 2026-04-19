import asyncio
import os
import sys

import aiosqlite

# Ensure shared_memory can be imported
sys.path.append(os.getcwd())


async def investigate():
    db_path = "shared_memory.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    print(f"--- Investigating database: {db_path} ---")

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # 1. Check schema_migrations
        try:
            cursor = await conn.execute("SELECT * FROM schema_migrations")
            migrations = await cursor.fetchall()
            print(f"Applied Migrations: {[dict(m) for m in migrations]}")
        except aiosqlite.OperationalError:
            print("schema_migrations table does not exist yet.")

        # 2. Check current schema for relations
        async with conn.execute("SELECT sql FROM sqlite_master WHERE name='relations'") as cursor:
            row = await cursor.fetchone()
            if row:
                print(f"\nRelations Schema:\n{row['sql']}")
                if "FOREIGN KEY" in row["sql"].upper():
                    print("!!! WARNING: FOREIGN KEY still exists in relations table.")
                else:
                    print("SUCCESS: FOREIGN KEY removed from relations table.")

        # 3. Check current schema for observations
        async with conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='observations'"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                print(f"\nObservations Schema:\n{row['sql']}")
                if "FOREIGN KEY" in row["sql"].upper():
                    print("!!! WARNING: FOREIGN KEY still exists in observations table.")
                else:
                    print("SUCCESS: FOREIGN KEY removed from observations table.")

        # 4. Check data counts
        tables = ["entities", "relations", "observations", "bank_files"]
        print("\n--- Data Counts ---")
        for table in tables:
            try:
                async with conn.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                    count = (await cursor.fetchone())[0]
                    print(f"{table}: {count} records")
            except Exception as e:
                print(f"{table}: Failed to count records ({e})")


if __name__ == "__main__":
    asyncio.run(investigate())
