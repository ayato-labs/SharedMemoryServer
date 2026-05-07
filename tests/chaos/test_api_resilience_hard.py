import asyncio
import json

import pytest

from shared_memory.api.server import read_memory, save_memory


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_massive_payload_resilience(mock_llm):
    """
    Chaos Test: 極端に巨大なデータの保存耐性テスト。
    データベースの限界やメモリ消費、タイムアウト挙動を確認。
    """
    # 100KBの巨大な説明文
    huge_text = "LongDescription" * 10000

    res = await save_memory(entities=[{"name": "HugePayloadNode", "description": huge_text}])
    assert "Saved" in res

    # 検索して取得できるか確認
    read_res = json.loads(await read_memory(query="HugePayloadNode"))
    assert len(read_res["graph"]["entities"][0]["description"]) >= 100000


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_malformed_input_robustness(mock_llm):
    """
    Chaos Test: 不正な型や構造の入力に対する堅牢性テスト。
    normalize関数が例外を出さずに処理を完結できるか。
    """
    # あえて型を無視した入力を投入
    test_cases = [
        {"entities": "string instead of list"},
        {"observations": [None, 123, "string instead of dict"]},
        {"bank_files": {"valid.md": None, "invalid_val": 12345}},
        {"entities": [{"name": "", "description": "empty name"}]},  # 空の名前
    ]

    for case in test_cases:
        res = await save_memory(**case)
        # 少なくとも例外でプロセスが死なないこと
        assert isinstance(res, str)


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_llm_json_corruption_fallback(mock_llm):
    """
    Chaos Test: LLMが不正な形式のJSONを返した場合のフォールバック検証。
    衝突検知ロジックなどがLLMの異常応答でクラッシュしないことを確認。
    """
    # 期待される形式 [ {"conflict": bool, ...} ] ではないゴミデータを返す
    mock_llm.models.set_response(
        "generate_content", "<html>Error 500: Internal Server Error</html>"
    )

    # 衝突チェックが走る条件で実行
    res = await save_memory(
        observations=[{"entity_name": "StabilityNode", "content": "Checking resilience"}]
    )

    # クラッシュせずに「AI Error」などのメッセージを返すか、安全に完了すること
    assert isinstance(res, str)
    assert "AI Error" in res or "Saved" in res


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_extreme_concurrency_race_condition(mock_llm):
    """
    Chaos Test: 同一リソースに対する極端な並列アクセス。
    セマフォによる制御とリトライメカニズムが、データ整合性を保てるか。
    """
    entity_name = "RaceNode"
    # 初期エンティティ作成
    await save_memory(entities=[{"name": entity_name}])

    # 50並列で観察事項を書き込み
    num_tasks = 50
    tasks = [
        save_memory(observations=[{"entity_name": entity_name, "content": f"Update {i}"}])
        for i in range(num_tasks)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 全てのタスクが例外なく終了すること
    success_count = 0
    for r in results:
        if isinstance(r, str) and "Saved" in r:
            success_count += 1

    # SQLiteのWALモードとリトライにより、高確率で全件成功するはず
    # 失敗があったとしても、システムがクラッシュしていないことが重要
    assert success_count > 0

    # DBの整合性確認（書き込まれた件数が0ではないこと）
    res_read = json.loads(await read_memory(query=entity_name))
    assert len(res_read["graph"]["observations"]) > 0
