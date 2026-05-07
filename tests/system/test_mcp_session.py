import pytest

from shared_memory.api import server


@pytest.mark.asyncio
@pytest.mark.system
async def test_mcp_tool_session_flow(mock_llm):
    """
    総合テスト: 実際のMCPツール呼び出しフローを模倣。
    1. save_memory で情報を蓄積
    2. sequential_thinking で思考を整理
    3. get_insights で結果を確認
    """
    # 背景の初期化を待たずに済むように、テスト内では初期化済みフラグを立てるか、
    # 実際に応答を待機するように ensure_initialized を利用する
    if server._INITIALIZED_EVENT is None:
        import asyncio

        server._INITIALIZED_EVENT = asyncio.Event()
    server._INITIALIZED_EVENT.set()

    # 1. 保存
    save_resp = await server.save_memory(
        entities=[{"name": "ThoughtNode", "description": "Used in thinking"}]
    )
    assert "Saved" in save_resp

    # 2. 思考の実行
    think_resp_raw = await server.sequential_thinking(
        thought="I need to analyze ThoughtNode based on the gathered memory.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="session_123",
    )
    import json

    think_resp = json.loads(think_resp_raw)
    assert "thoughtNumber" in think_resp

    # 3. インサイトの取得
    from shared_memory.common.tasks import wait_for_background_tasks

    await wait_for_background_tasks()
    insights_raw = await server.get_insights(format="json")
    insights = json.loads(insights_raw)
    assert "facts" in insights
    assert insights["facts"]["stored_entities"] >= 1
