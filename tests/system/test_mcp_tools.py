import json

import pytest

from shared_memory.api import server


@pytest.mark.asyncio
async def test_mcp_save_search_reason_flow(mock_llm):
    """
    総合テスト: ユーザーのメインフロー (保存 -> 検索 -> 思考) が一貫して動作するか。
    """
    # 1. 初期化待ち (server.ensure_initialized)
    await server.ensure_initialized()

    # 2. 知識の保存 (MCP Tool: save_memory)
    save_res = await server.save_memory(
        entities=[{"name": "ProjectX", "description": "Confidential AI project"}]
    )
    assert "Processing" in save_res

    # バックグラウンドタスクの完了を待機
    await server.wait_for_background_tasks(timeout=5.0)

    # 3. 知識の検索 (MCP Tool: read_memory)
    search_res = await server.read_memory(query="ProjectX")
    assert "Confidential AI project" in search_res

    # 4. 思考の実行 (MCP Tool: sequential_thinking)
    # LLMが結論を出すようなモック
    mock_llm.models.set_response(
        "generate_content",
        json.dumps(
            {
                "action": "final_answer",
                "answer": "ProjectX is strategically important.",
                "thought_process": "Based on retrieved info.",
            }
        ),
    )

    thinking_res = await server.sequential_thinking(
        thought="Evaluate ProjectX", thought_number=1, total_thoughts=1, next_thought_needed=False
    )

    assert "strategically important" in thinking_res
