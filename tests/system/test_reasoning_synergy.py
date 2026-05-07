import asyncio
import json

import pytest

from shared_memory.api.server import (
    ensure_initialized,
    get_insights,
    read_memory,
    sequential_thinking,
    wait_for_background_tasks,
)


@pytest.mark.asyncio
@pytest.mark.system
async def test_reasoning_and_distillation_system_flow(mock_llm):
    """
    System Test: 思考プロセスから知識の自動抽出、そしてインサイトへの反映までの
    エンドツーエンドのフローを検証。
    """
    await ensure_initialized()
    session_id = "system_session_abc"

    # 1. 思考プロセスの実行
    # 思考の過程で新しい知識（例: "Project X is coded in Rust"）が生まれる想定
    await sequential_thinking(
        thought="I am analyzing Project X. It is a distributed system written in Rust.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_id,
    )

    # 2. 思考の完了と自動抽出
    # ここでは Mock LLM が Rust エンティティを抽出したと仮定する応答を設定
    mock_llm.models.set_response(
        "generate_content",
        json.dumps(
            {
                "entities": [
                    {"name": "Project X", "entity_type": "project", "description": "Rust system"}
                ],
                "relations": [],
                "observations": [{"entity_name": "Project X", "content": "Written in Rust"}],
            }
        ),
    )

    await sequential_thinking(
        thought="Conclusion: Rust provides safety for Project X.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id=session_id,
    )

    # バックグラウンドタスクの完了を待つ
    await wait_for_background_tasks(timeout=5.0)

    # 3. 抽出された知識の検索検証
    # Direct DB Check for debugging
    from shared_memory.infra.database import async_get_connection

    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM entities WHERE name='Project X'")
        row = await cursor.fetchone()
        if not row:
            # Maybe it was saved with a different name or didn't save?
            cursor = await conn.execute("SELECT name FROM entities")
            all_names = [r[0] for r in await cursor.fetchall()]
            print(f"DEBUG: All entities in DB: {all_names}")
        else:
            print("DEBUG: 'Project X' found in direct DB query.")

    # Perform several attempts to wait for DB sync if needed
    for _ in range(3):
        res_read_raw = await read_memory(query="Project X")
        res_read = json.loads(res_read_raw)
        entity_names = [e["name"] for e in res_read["graph"]["entities"]]
        if "Project X" in entity_names:
            break
        await asyncio.sleep(1.0)

    if "Project X" not in entity_names:
        # Fallback keyword search
        res_read_raw = await read_memory(query="Rust system")
        res_read = json.loads(res_read_raw)
        entity_names = [e["name"] for e in res_read["graph"]["entities"]]

    assert "Project X" in entity_names

    # 4. 全体統計の確認
    insights_raw = await get_insights(format="json")
    insights_data = json.loads(insights_raw)

    # get_insights (json) returns keys under 'facts' like 'stored_entities'
    assert insights_data["facts"]["stored_entities"] >= 1
    # also check if the Project X observation is counted (though it might be in 'stored_entities' or similar)
