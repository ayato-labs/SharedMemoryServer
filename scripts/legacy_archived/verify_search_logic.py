import re
import sqlite3


# 1. Setup Mock Database
def setup_mock_db():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # 既存のテーブル構造を模倣
    cursor.execute("""
        CREATE TABLE entities (
            name TEXT PRIMARY KEY,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT,
            content TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE bank_files (
            filename TEXT PRIMARY KEY,
            content TEXT
        )
    """)

    # テストデータの投入
    entities = [
        (
            "SharedMemoryServer",
            "A central repository for agent memories using graph and bank storage.",
        ),
        ("FastMCP", "A framework for building MCP servers quickly in Python."),
        ("SQLite", "A lightweight, file-based database engine used for storage."),
    ]
    cursor.executemany("INSERT INTO entities (name, description) VALUES (?, ?)", entities)

    observations = [
        ("SharedMemoryServer", "Integrated SQLite for persistent storage of graphs."),
        ("SharedMemoryServer", "Uses FastMCP as the communication layer."),
        ("SQLite", "Supports WAL mode for better concurrency."),
    ]
    cursor.executemany(
        "INSERT INTO observations (entity_name, content) VALUES (?, ?)", observations
    )

    bank_files = [
        (
            "server.py",
            "mcp = FastMCP('SharedMemoryServer'). Logic handles save_memory and read_memory.",
        ),
        ("database.py", "sqlite3 connection logic with retry_on_db_lock decorator."),
    ]
    cursor.executemany("INSERT INTO bank_files (filename, content) VALUES (?, ?)", bank_files)

    conn.commit()
    return conn


# 2. Improved Keyword Search Logic
def keyword_search(conn: sqlite3.Connection, query: str) -> list[tuple[str, str, float]]:
    """
    一致度（スコア）を計算するキーワード検索。
    - 完全一致: 10.0
    - 部分一致 (単語単位): 5.0
    - あいまい一致 (LIKE): 1.0
    """
    cursor = conn.cursor()
    query_words = re.findall(r"\w+", query.lower())

    scored_results = {}

    data_sources = [
        ("entities", "name", "description"),
        ("observations", "entity_name", "content"),
        ("bank_files", "filename", "content"),
    ]

    for table, id_col, content_col in data_sources:
        cursor.execute(f"SELECT {id_col}, {content_col} FROM {table}")
        rows = cursor.fetchall()

        for row_id, content in rows:
            content_lower = str(content).lower()
            row_id_lower = str(row_id).lower()
            score = 0.0

            # 1. ID/Name への一致は高評価
            if query.lower() == row_id_lower:
                score += 10.0
            elif query.lower() in row_id_lower:
                score += 5.0

            # 2. コンテンツ内キーワード一致
            for word in query_words:
                if word in content_lower:
                    # 単語としての出現回数をカウント
                    count = content_lower.count(word)
                    score += count * 1.5

            if score > 0:
                key = (table, row_id)
                scored_results[key] = scored_results.get(key, 0.0) + score

    # フォーマットしてソート
    sorted_results = sorted(
        [(k[0], k[1], s) for k, s in scored_results.items()],
        key=lambda x: x[2],
        reverse=True,
    )

    return sorted_results


# 3. Validation Run
if __name__ == "__main__":
    conn = setup_mock_db()

    test_queries = [
        "SharedMemoryServer",
        "FastMCP",
        "SQLite concurrency",
        "persistence",
    ]

    print("=== Keyword Search Validation Results ===\n")
    print(f"{'Source':<15} | {'ID':<20} | {'Score':<5}")
    print("-" * 45)

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        matches = keyword_search(conn, q)
        if matches:
            for source, row_id, score in matches:
                print(f"{source:<15} | {row_id:<20} | {score:<5.1f}")
        else:
            print("No matches found.")

    conn.close()
