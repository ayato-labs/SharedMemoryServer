import asyncio
import random
import pytest
import aiosqlite
from ripen.core.logic import save_memory_core, read_memory_core
from ripen.infra.database import async_get_connection, get_db_path
from ripen.common.tasks import wait_for_background_tasks

@pytest.mark.asyncio
async def test_extreme_concurrency_and_data_durability(fake_llm):
    """
    厳しいテスト: 極限の並列書き込み条件下でのデータ耐久性と整合性の検証。
    10個の並列リクエストが、同一のエンティティに対して異なる観察を同時に投入し、
    データベースがデッドロックせずにすべての情報を正確に永続化できるかを確認する。
    """
    entity_name = "ChaosEntity"
    num_concurrent = 10
    
    # 1. 初期エンティティの作成
    await save_memory_core(entities=[{"name": entity_name, "description": "Resilience test target"}])

    # 2. 並列書き込みタスクの生成
    async def worker(worker_id):
        # わずかなランダムディレイを入れて競合を激化させる
        await asyncio.sleep(random.uniform(0.01, 0.1))
        content = f"Observation from worker {worker_id}"
        result = await save_memory_core(
            observations=[{"entity_name": entity_name, "content": content}],
            agent_id=f"worker_{worker_id}"
        )
        return result

    # 3. 同時実行
    tasks = [worker(i) for i in range(num_concurrent)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. バックグラウンドタスク（蒸留など）の完了を待機
    await wait_for_background_tasks(timeout=10.0)

    # 5. データベースの裏取り調査 (物理整合性チェック)
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 投入したすべての観察が漏れなく保存されているか
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM observations WHERE entity_name = ?",
            (entity_name,)
        )
        row = await cursor.fetchone()
        count = row["cnt"]
        
        # すべて成功していれば num_concurrent 個あるはず
        assert count == num_concurrent, f"Data loss detected! Expected {num_concurrent}, got {count}"
        
        # 監査ログとの照合 (裏取り)
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM audit_logs WHERE table_name = 'observations' AND content_id = ?",
            (entity_name,)
        )
        row = await cursor.fetchone()
        assert row["cnt"] == num_concurrent, "Audit logs are missing for some operations"
        
        # 重要度（Importance）の累積チェック
        cursor = await conn.execute("SELECT importance FROM entities WHERE name = ?", (entity_name,))
        importance = (await cursor.fetchone())[0]
        # 初期5 + 10回更新 = 15 だが、上限10のはず
        assert importance == 10, f"Importance logic failed. Expected 10, got {importance}"

    # 6. 検索による最終確認
    search_result = await read_memory_core(query=entity_name)
    observations = search_result["graph"]["observations"]
    assert len(observations) == num_concurrent
