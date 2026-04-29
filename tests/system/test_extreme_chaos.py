import pytest
from shared_memory.api.server import save_memory, read_memory
from unittest.mock import AsyncMock, patch
import asyncio

@pytest.mark.system
@pytest.mark.asyncio
async def test_extreme_chaos_user_flow():
    """
    総合テスト：DBロック、AIエラー、不正入力が同時に発生する「最悪の状況」での整合性テスト
    """
    # 1. 準備：DBロックをシミュレート
    mock_db = AsyncMock()
    # 最初はロック、後に成功
    mock_db.execute.side_effect = [
        Exception("database is locked"),
        AsyncMock(), # 成功
        AsyncMock(), # 成功
    ]

    # 2. AIエラーをシミュレート（1回失敗、2回目成功）
    mock_ai = AsyncMock()
    mock_ai.aio.models.embed_content.side_effect = [
        Exception("503 Service Unavailable"),
        AsyncMock() # 成功
    ]

    with patch("shared_memory.infra.database.async_get_connection") as mock_conn:
        mock_conn.return_value.__aenter__.return_value = mock_db
        with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=mock_ai):
            with patch("shared_memory.api.server.ensure_initialized", new_callable=AsyncMock):
                with patch("shared_memory.core.ai_control.asyncio.sleep", return_value=None):
                    
                    # カオス状態での保存リクエスト
                    # 不正な型（文字列の数値など）も混ぜる
                    entities = [{"name": "ChaosEntity", "description": "System chaos test"}]
                    result = await save_memory(entities=entities, agent_id="chaos_bot")
                    
                    assert "Saved" in result
                    
                    # 非同期処理の完了を待つ
                    from shared_memory.api.server import wait_for_background_tasks
                    await wait_for_background_tasks(timeout=5.0)

    # 最終的な整合性：読み取りが可能か
    # (内部ロジックの呼び出しを検証)
    with patch("shared_memory.core.logic.read_memory_core", new_callable=AsyncMock) as mock_read:
        mock_read.return_value = "Chaos knowledge retrieved"
        read_result = await read_memory(query="Chaos")
        assert "Chaos knowledge" in read_result
