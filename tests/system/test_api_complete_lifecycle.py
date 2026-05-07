import json

import pytest

from shared_memory.api.server import (
    ensure_initialized,
    get_insights,
    read_memory,
    save_memory,
    synthesize_entity,
)


@pytest.mark.asyncio
@pytest.mark.system
async def test_api_complete_lifecycle_system(mock_llm):
    """
    System Test: ユーザーの一連のワークフローを包括的に検証。

    シナリオ:
    1. AIエージェントが新しい知識（エンティティと観察）を保存する。
    2. 保存した知識をクエリで検索し、正しく返されるか確認する。
    3. 特定のエンティティについて知識の合成（要約）を依頼する。
    4. システム全体のインサイト（レポート）を取得し、知識が反映されているか確認する。
    """
    # サーバーの初期化を確実にする
    await ensure_initialized()

    # 1. 記憶の保存 (MCP Tool 経由)
    res_save = await save_memory(
        entities=[{"name": "SystemLifecycleNode", "description": "Node for lifecycle testing"}],
        observations=[
            {"entity_name": "SystemLifecycleNode", "content": "Lifecycle test is in progress"}
        ],
    )
    assert "Saved" in res_save

    # 2. 検索と検証 (MCP Tool 経由)
    res_read_raw = await read_memory(query="Lifecycle")
    res_read = json.loads(res_read_raw)

    # エンティティが含まれているか
    entity_names = [e["name"] for e in res_read["graph"]["entities"]]
    assert "SystemLifecycleNode" in entity_names

    # 観察事項が含まれているか
    obs_contents = [o["content"] for o in res_read["graph"]["observations"]]
    assert "Lifecycle test is in progress" in obs_contents

    # 3. 知識合成の実行 (MCP Tool 経由)
    # LLMの応答をシミュレート
    mock_llm.models.set_response(
        "generate_content",
        "Synthesis Report: SystemLifecycleNode is a test subject for the complete workflow.",
    )

    res_synth_raw = await synthesize_entity(entity_name="SystemLifecycleNode")
    res_synth = json.loads(res_synth_raw)
    assert "Synthesis Report" in res_synth

    # 4. システムインサイトの取得 (MCP Tool 経由)
    res_insights = await get_insights(format="markdown")

    # 基本的なレポート項目が含まれているか
    assert "# SharedMemory" in res_insights
    # 局所化（日本語）されている可能性があるため、柔軟に検証
    assert "エンティティ" in res_insights or "Entities" in res_insights
    # 少なくとも1つのエンティティが存在することが統計に反映されているはず
    assert "1" in res_insights
