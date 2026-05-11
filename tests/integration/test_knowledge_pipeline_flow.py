import pytest

from ripen.core.logic import read_memory_core, save_memory_core


@pytest.mark.asyncio
async def test_knowledge_pipeline_integration(mock_llm):
    """
    結合テスト: 複数の関数（保存 -> 検索）が連携して動作することを検証。
    LLMはMock化することを許可されている。
    """
    # LLMのレスポンスをMockで設定
    mock_llm.generate_content.return_value = '{"conflict": false, "reason": "Mocked safe status"}'

    # 1. データの保存
    save_result = await save_memory_core(
        entities=[{"name": "IntegrationEntity", "description": "Flow test"}]
    )
    assert "SAVED" in save_result.upper()

    # 2. データの検索 (内部で search.perform_search -> database を呼ぶ)
    read_result = await read_memory_core(query="IntegrationEntity")

    # 3. 検証
    # read_memory_core は {"graph": ..., "bank": ...} を返す
    assert "IntegrationEntity" in str(read_result["graph"])

    # 裏取り: 実際にDBに1件入っているか
    from ripen.infra.database import async_get_connection

    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM entities WHERE name = 'IntegrationEntity'"
        )
        row = await cursor.fetchone()
        assert row["cnt"] == 1
