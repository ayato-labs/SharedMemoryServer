import pytest

from shared_memory.api import server
from shared_memory.core import logic


@pytest.mark.asyncio
async def test_llm_malformed_json_resilience(mock_llm):
    """
    異常系テスト: LLMが不正なJSONを返した場合、システムがクラッシュせずに適切にハンドルするか。
    """
    await server.ensure_initialized()

    # 不正なJSONをモック
    mock_llm.models.set_response("generate_content", "INVALID_JSON{")

    # 思考実行 (内部でJSONパースに失敗するはず)
    result = await server.sequential_thinking(
        thought="Cause an error", thought_number=1, total_thoughts=1, next_thought_needed=False
    )

    # エラーメッセージが返るか、あるいはフォールバックが機能しているか
    # 現状の実装では例外をキャッチしてユーザーに通知するはず
    assert "error" in result.lower() or "failed" in result.lower()


@pytest.mark.asyncio
async def test_llm_quota_exhaustion_retry(mock_llm):
    """
    異常系テスト: LLMが429 (Quota Exhausted) を返した場合にリトライが行われるか。
    """
    await server.ensure_initialized()

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 1回目は429エラーを模倣
            raise Exception("429 Resource has been exhausted (Retry in 0.1s)")
        # 2回目は成功
        res = MagicMock()
        res.text = '{"conflict": false}'
        return res

    mock_llm.models.generate_content.side_effect = side_effect

    # 保存実行 (内部でリトライが走るはず)
    # logic.save_memory_core は @retry_on_ai_quota がついている前提
    # (server.save_memory 経由だとバックグラウンドになるため、直接コアを呼ぶか、待ちを設ける)
    result = await logic.save_memory_core(
        entities=[{"name": "RetryNode", "description": "Testing quota retry"}]
    )

    assert "Saved 1 entities" in result
    assert call_count >= 2  # 少なくとも1回のリトライが行われた


@pytest.mark.asyncio
async def test_empty_entities_input_safety():
    """境界値テスト: 空のエンティティリストを渡した場合。"""
    await server.ensure_initialized()
    result = await server.save_memory(entities=[])
    assert "No valid entities" in result or "Skipped" in result


from unittest.mock import MagicMock
