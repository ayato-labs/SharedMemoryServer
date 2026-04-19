import os
import sqlite3

db_path = "shared_memory.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = ["entities", "relations", "observations"]
    for table in tables:
        try:
            cursor.execute(f"SELECT count(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count}")
        except Exception as e:
            print(f"Error reading {table}: {e}")

    conn.close()

bank_dir = "memory-bank"
if os.path.exists(bank_dir):
    files = [f for f in os.listdir(bank_dir) if f.endswith(".md")]
    print(f"Bank files: {len(files)}")
    for f in files:
        print(f" - {f}")
else:
    # try 'bank' dir too
    bank_dir = "bank"
    if os.path.exists(bank_dir):
        files = [f for f in os.listdir(bank_dir) if f.endswith(".md")]
        print(f"Bank files: {len(files)}")
        for f in files:
            print(f" - {f}")
