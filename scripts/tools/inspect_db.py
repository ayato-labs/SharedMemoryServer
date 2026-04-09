import os
import sqlite3

db_path = ".shared_memory/thoughts.db"
print(f"Checking DB: {db_path}")
if not os.path.exists(db_path):
    print("DB file does not exist!")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print(f"Tables: {tables}")
    if ('thought_history',) in tables:
        cur.execute("SELECT COUNT(*) FROM thought_history")
        print(f"Thought history count: {cur.fetchone()[0]}")
    conn.close()
