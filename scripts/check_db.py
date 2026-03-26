import sqlite3


def check_db():
    conn = sqlite3.connect("shared_memory.db")
    cursor = conn.cursor()

    print("--- troubleshooting_knowledge ---")
    cursor.execute("SELECT * FROM troubleshooting_knowledge")
    rows = cursor.fetchall()
    for r in rows:
        print(r)

    print("\n--- embeddings count ---")
    cursor.execute("SELECT count(*) FROM embeddings WHERE content_id LIKE 'ts_%'")
    print(cursor.fetchone()[0])

    conn.close()


if __name__ == "__main__":
    check_db()
