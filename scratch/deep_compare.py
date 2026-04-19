import asyncio

import aiosqlite


async def deep_compare(db1, db2):
    print(f"Comparing {db1} (Current) and {db2} (Backup)\n")

    async with aiosqlite.connect(db1) as conn1, aiosqlite.connect(db2) as conn2:
        conn1.row_factory = aiosqlite.Row
        conn2.row_factory = aiosqlite.Row

        tables = ["entities", "relations", "observations"]

        for table in tables:
            print(f"--- Table: {table} ---")

            # 1. Compare Counts
            async with conn1.execute(f"SELECT COUNT(*) FROM {table}") as c1:
                count1 = (await c1.fetchone())[0]
            async with conn2.execute(f"SELECT COUNT(*) FROM {table}") as c2:
                count2 = (await c2.fetchone())[0]

            print(f"Counts: Current={count1}, Backup={count2}")
            if count1 != count2:
                print(f"!!! ALERT: Count mismatch in {table}")

            # 2. Compare Content (Sample or Hash-like check)
            # We'll fetch all data and compare rows
            async with conn1.execute(f"SELECT * FROM {table} ORDER BY 1") as c1:
                rows1 = [dict(r) for r in await c1.fetchall()]
            async with conn2.execute(f"SELECT * FROM {table} ORDER BY 1") as c2:
                rows2 = [dict(r) for r in await c2.fetchall()]

            if rows1 == rows2:
                print("Content: Perfectly identical.")
            else:
                print(f"!!! ALERT: Content differs in {table}")
                # Show first difference if any
                for i in range(min(len(rows1), len(rows2))):
                    if rows1[i] != rows2[i]:
                        print(f"Difference at row {i}:")
                        print(f"  Current: {rows1[i]}")
                        print(f"  Backup:  {rows2[i]}")
                        break
            print()

        # 3. Schema Check for FKs
        print("--- Schema Verification ---")
        async with conn1.execute("SELECT sql FROM sqlite_master WHERE name='relations'") as c1:
            sql1 = (await c1.fetchone())[0]
        async with conn2.execute("SELECT sql FROM sqlite_master WHERE name='relations'") as c2:
            sql2 = (await c2.fetchone())[0]

        print(f"Current Relations FK: {'Yes' if 'FOREIGN KEY' in sql1.upper() else 'No'}")
        print(f"Backup Relations FK: {'Yes' if 'FOREIGN KEY' in sql2.upper() else 'No'}")


if __name__ == "__main__":
    db_current = "shared_memory.db"
    db_backup = "shared_memory.db.20260419181117.bak"
    asyncio.run(deep_compare(db_current, db_backup))
