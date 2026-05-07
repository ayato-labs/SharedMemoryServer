from unittest.mock import MagicMock, patch

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
    result_raw = await server.sequential_thinking(
        thought="Cause an error", thought_number=1, total_thoughts=1, next_thought_needed=False
    )

    import json

    result = json.loads(result_raw)

    # 現状の実装では内部で例外がキャッチされ、思考結果は返るが抽出はスキップされる。
    # ツール自体がクラッシュしていないことを確認。
    assert "thoughtNumber" in result


@pytest.mark.asyncio
async def test_llm_quota_exhaustion_retry(mock_llm):
    """
    異常系テスト: LLMが429 (Quota Exhausted) を返した場合にリトライが行われるか。
    """
    await server.ensure_initialized()

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 Resource has been exhausted")

        # Return a mock embedding response
        mock_resp = MagicMock()
        mock_resp.embeddings = [MagicMock(values=[0.1] * 768)]
        return mock_resp

    # Force Gemini engine
    with patch.dict("os.environ", {"EMBEDDING_ENGINE": "gemini", "GOOGLE_API_KEY": "fake"}):
        with patch("shared_memory.infra.embeddings.get_gemini_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.aio.models.embed_content.side_effect = side_effect
            mock_factory.return_value = mock_client

            with patch("shared_memory.core.ai_control.asyncio.sleep", return_value=None):
                result = await logic.save_memory_core(
                    entities=[{"name": "RetryNode", "description": "Testing quota retry"}]
                )

                assert "Saved 1 entities" in result
                assert call_count >= 2


@pytest.mark.asyncio
async def test_empty_entities_input_safety():
    """境界値テスト: 空のエンティティリストを渡した場合。"""
    await server.ensure_initialized()
    result = await server.save_memory(entities=[])
    # save_memory_core returns "save_memory_core success: ..." or similar
    assert "success" in result.lower() or result == ""
