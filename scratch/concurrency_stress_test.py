import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory import database, thought_logic, logic
from shared_memory.utils import get_db_path

async def simultaneous_call(call_id):
    """一つの並列タスクとして検索を実行"""
    try:
        # read_memory_core は内部で async_get_connection (蛇口) を呼び出す
        await logic.read_memory_core("test query")
        return f"Task {call_id}: Success"
    except Exception as e:
        return f"Task {call_id}: FAILED with {type(e).__name__}: {e}"

async def concurrency_test():
    db_path = get_db_path()
    
    # 1. 状態を最悪にする (DB削除 + フラグリセット)
    if os.path.exists(db_path):
        os.remove(db_path)
    database._DB_INITIALIZED = False
    thought_logic._THOUGHTS_INITIALIZED = False
    
    print("--- CONCURRENCY ATTACK START ---")
    print("Scenario: 50 tasks simultaneously trying to initialize an empty database.")

    # 2. 50個のタスクを一斉に起動
    tasks = [simultaneous_call(i) for i in range(50)]
    results = await asyncio.gather(*tasks)

    # 3. 結果の集計
    success_count = sum(1 for r in results if "Success" in r)
    failure_count = len(results) - success_count
    
    print("\n--- TEST RESULTS ---")
    print(f"Total Tasks: {len(results)}")
    print(f"Successes: {success_count}")
    print(f"Failures:  {failure_count}")

    if failure_count > 0:
        print("\nDEBUG: Detected race condition errors:")
        for r in results:
            if "FAILED" in r:
                print(f"  {r}")
    else:
        print("\nPerfect! The system handled simultaneous initialization without a single error.")

if __name__ == "__main__":
    asyncio.run(concurrency_test())
