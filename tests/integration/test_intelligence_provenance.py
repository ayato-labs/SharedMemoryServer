import pytest

from shared_memory.core import logic, search
from shared_memory.infra.database import async_get_connection


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_provenance_integration(mock_llm):
    """
    Integration Test: データの保存 -> 検索 -> 知識合成 のパイプラインを検証。
    情報の裏取り（Database への直接アクセス）を含めて詳細に分析する。
    """
    entity_name = "ProvenanceNode"
    # 1. データの保存
    await logic.save_memory_core(
        entities=[{"name": entity_name, "description": "Analyzing data sources"}],
        observations=[
            {"entity_name": entity_name, "content": "Source A says X"},
            {"entity_name": entity_name, "content": "Source B says Y"},
        ],
    )

    # 2. DBでの情報の裏取り
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM observations WHERE entity_name=?", (entity_name,)
        )
        count = (await cursor.fetchone())[0]
        assert count == 2, f"Expected 2 observations in DB for {entity_name}, found {count}"

    # 3. 検索の実行
    # キーワード検索とセマンティック検索が組み合わさっているか
    graph_data, bank_data = await search.perform_search("Source A")
    obs_contents = [o["content"] for o in graph_data["observations"]]
    assert "Source A says X" in obs_contents

    # 4. 知識合成の実行 (Mock LLM を使用)
    mock_llm.models.set_response(
        "generate_content", f"Consolidated view for {entity_name}: Both X and Y are reported."
    )

    summary = await search.synthesize_knowledge(entity_name)
    assert "Both X and Y" in summary

    # 5. 監査ログの整合性確認
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT table_name, action FROM audit_logs WHERE content_id=?", (entity_name,)
        )
        logs = await cursor.fetchall()
        actions = [log["action"] for log in logs]
        assert "INSERT" in actions or "UPDATE" in actions
