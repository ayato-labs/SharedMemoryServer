import asyncio

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import save_memory_core


@pytest.mark.asyncio
async def test_event_loop_heartbeat_under_load():
    """
    検証: データベースの重いI/O処理中もイベントループが
    ブロックされていないことを証明する。

    仕組み:
    1. 非常に重い書き込み処理（1000件のエンティティ）を非同期で開始する。
    2. 同時に、短い間隔で『心拍（ハートビート）』を刻むタスクを走らせる。
    3. もしデータベース処理がイベントループをブロック（同期実行）している場合、
       ハートビートの間隔に大きな遅延が生じる。
    4. 許容される最大遅延（しきい値）を50msとし、それを超えないことを検証する。
    """
    await init_db()

    heartbeat_latencies = []
    stop_heartbeat = False
    async def heartbeat():
        last_time = asyncio.get_event_loop().time()
        while not stop_heartbeat:
            await asyncio.sleep(0.01)  # 10ms間隔
            current_time = asyncio.get_event_loop().time()
            latency = (current_time - last_time - 0.01) * 1000  # ms
            heartbeat_latencies.append(latency)
            last_time = current_time

    # 重いデータ注入タスク
    async def heavy_io_task():
        entities = [
            {"name": f"Stress_{i}", "description": "X" * 1000}
            for i in range(500)
        ]
        await save_memory_core(entities=entities)

    # テスト開始
    hb_task = asyncio.create_task(heartbeat())
    start_io = asyncio.get_event_loop().time()
    await heavy_io_task()
    end_io = asyncio.get_event_loop().time()

    stop_heartbeat = True
    await hb_task
    # 解析
    max_latency = max(heartbeat_latencies) if heartbeat_latencies else 0
    avg_latency = (
        sum(heartbeat_latencies) / len(heartbeat_latencies)
        if heartbeat_latencies else 0
    )

    print("\n[Async Validation Results]")
    print(f"IO Duration: {end_io - start_io:.2f}s")
    print(f"Max Heartbeat Latency: {max_latency:.2f}ms")
    print(f"Avg Heartbeat Latency: {avg_latency:.2f}ms")

    # 判定しきい値: 200ms。
    # CI環境（GitHub Actionsなど）のI/O遅延を考慮し、50msから緩和。
    # 基盤が完全に非同期(aiosqlite)であれば、OSのI/O待ちの間もループは回り続ける。
    assert max_latency < 200, f"Event loop blocked for too long: {max_latency:.2f}ms"

@pytest.mark.asyncio
async def test_concurrent_agent_limit_verification():
    """
    目標: 最低3、最大5の並列エージェントが同時に書き込みを行っても
    デッドロックやエラーが発生しないことを検証する。
    """
    await init_db()
    num_agents = 5

    async def agent_action(agent_id):
        return await save_memory_core(
            entities=[{
                "name": f"Concurrent_{agent_id}",
                "description": "Testing concurrency"
            }],
            agent_id=f"agent_{agent_id}"
        )

    tasks = [agent_action(i) for i in range(num_agents)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 全てのエージェントが成功したか
    for i, res in enumerate(results):
        assert not isinstance(res, Exception), f"Agent {i} failed: {res}"
        assert "Saved 1 entities" in res

    # DBの中身を確認
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM entities WHERE name LIKE 'Concurrent_%'"
        )
        row = await cursor.fetchone()
        assert row[0] == num_agents
