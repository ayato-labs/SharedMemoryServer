import sqlite3


def check_db(path):
    print(f"Checking {path}")
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        conn.close()
    except Exception as e:
        print(f"Error checking {path}: {e}")


if __name__ == "__main__":
    check_db("shared_memory.db")
    check_db("shared_memory.db.20260419181117.bak")
