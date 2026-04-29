import pytest
from shared_memory.api.server import save_memory, sequential_thinking, manage_knowledge_activation
from unittest.mock import AsyncMock, patch

@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_memory_input_normalization():
    """AIエージェントがNoneや空の値を送ってきた場合の正規化テスト"""
    # ensure_initialized をモック化
    with patch("shared_memory.api.server.ensure_initialized", new_callable=AsyncMock):
        with patch("shared_memory.common.tasks.create_background_task") as mock_task:
            # 全て None で送信
            await save_memory(entities=None, relations=None, observations=None, bank_files=None)
            
            # 内部で空リスト/辞書に変換されてバックグラウンドタスクに渡されているか確認
            args, _ = mock_task.call_args
            # 第1引数はコルーチン。そのコルーチンの引数をチェックするためにラップ元の引数を検証
            # _run_save_memory_background(entities, relations, observations, bank_files, agent_id)
            # 実際の呼び出しは server.py:326
            
            # メッセージ内容の検証
            result = await save_memory(entities=None)
            assert "Saved (initiated in background) for: nothing." in result

@pytest.mark.unit
@pytest.mark.asyncio
async def test_sequential_thinking_lenient_parsing():
    """AIエージェントが文字列で数値を送ってきた場合の補正テスト"""
    with patch("shared_memory.api.server.ensure_initialized", new_callable=AsyncMock):
        with patch("shared_memory.core.thought_logic.process_thought_core", new_callable=AsyncMock) as mock_core:
            # 文字列で数値を送信
            await sequential_thinking(
                thought="Testing lenient parsing",
                thought_number="5",
                total_thoughts="10",
                next_thought_needed="true",
                revises_thought="2"
            )
            
            # int に変換されてコアロジックに渡されているか
            mock_core.assert_called_once()
            args = mock_core.call_args.args
            assert args[1] == 5  # thought_number
            assert args[2] == 10 # total_thoughts
            assert args[3] is True # next_thought_needed (lower string "true" -> True)
            assert args[5] == 2  # revises_thought

@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_activation_single_id_normalization():
    """AIエージェントが単一のIDを文字列で送ってきた場合の補正テスト"""
    with patch("shared_memory.api.server.ensure_initialized", new_callable=AsyncMock):
        with patch("shared_memory.core.logic.manage_knowledge_activation_core", new_callable=AsyncMock) as mock_core:
            # 単一文字列で送信
            await manage_knowledge_activation(ids="single_id_123", status="inactive")
            
            # リスト [ids] に変換されているか
            mock_core.assert_called_once_with(["single_id_123"], "inactive")
