import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory import database, thought_logic
from shared_memory.search import perform_keyword_search
from shared_memory.utils import get_db_path

async def stress_test():
    db_path = get_db_path()
    
    # 1. 意図的にDBを削除
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"DEBUG: Deleted existing DB: {db_path}")

    # 2. メモリ内の初期化済みフラグを強制的にリセット (意地悪な状態)
    database._DB_INITIALIZED = False
    thought_logic._THOUGHTS_INITIALIZED = False
    print("DEBUG: Reset global initialization flags to False.")

    print("\n--- ATTACK START ---")
    print("Scenario: Calling deep-layer function 'perform_keyword_search' directly, bypassing tool entry guards.")
    
    try:
        # ツールの入り口を通らずに、直接検索機能（統計ログ出力を伴う）を叩く
        # 本来ならここで no such table: search_stats が出るはず
        results = await perform_keyword_search("test query")
        
        print("\n--- RESULT ---")
        print("Success! The deep-layer guard automatically initialized the DB.")
        print(f"Results obtained: {len(results)}")
        
        # 実際にテーブルが存在するか、別の接続で確認
        import aiosqlite
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_stats'")
            if await cursor.fetchone():
                print("Proof: Table 'search_stats' exists in the fresh database.")
            else:
                print("Failure: Table 'search_stats' was NOT found.")

    except Exception as e:
        print(f"\n--- FAILURE ---")
        print(f"Scenario failed as expected in the OLD version: {e}")

if __name__ == "__main__":
    asyncio.run(stress_test())
