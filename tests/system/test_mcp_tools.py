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
    assert "Saved" in save_res

    # バックグラウンドタスクの完了を待機
    await server.wait_for_background_tasks(timeout=5.0)

    # 3. 遏･隴倥讀懃ｴ｢ (MCP Tool: read_memory)
    search_res_raw = await server.read_memory(query="ProjectX")
    search_res = json.loads(search_res_raw)
    assert "Confidential AI project" in str(search_res)

    # 4. 諤晁螳溯｡ (MCP Tool: sequential_thinking)
    # LLM縺檎ｵ占ｫ結論繧蜃ｺ縺吶ｈ縺↑繝｢繝け
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

    thinking_res_raw = await server.sequential_thinking(
        thought="Evaluate ProjectX", thought_number=1, total_thoughts=1, next_thought_needed=False
    )
    thinking_res = json.loads(thinking_res_raw)

    assert thinking_res["thoughtNumber"] == 1
