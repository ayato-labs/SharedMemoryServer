import json

import pytest

from ripen.core.logic import save_memory_core
from ripen.infra.database import async_get_connection
from ripen.ops import management


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_conflict_detection_and_resolution_flow(mock_llm):
    """
    Integration Test: 衝突検知からDashboard経由の解決、DB反映までの全フローを検証。
    """
    # 1. 初期データ準備 (衝突のベースとなる観察事項を1つ入れておく)
    await save_memory_core(
        entities=[{"name": "ConflictNode", "description": "Original description"}],
        observations=[{"entity_name": "ConflictNode", "content": "The sky is blue."}],
    )

    # 2. 衝突するデータの保存 (Mock LLM が conflict=True を返すように設定)
    mock_llm.models.set_response(
        "generate_content",
        json.dumps([{"conflict": True, "reason": "Explicit contradiction detected by LLM"}]),
    )

    # 新しい観察事項の保存試行 (既に1件あるので衝突チェックが走る)
    result = await save_memory_core(
        observations=[{"entity_name": "ConflictNode", "content": "The sky is green."}]
    )
    assert "CONFLICTS DETECTED" in result

    # 3. 衝突テーブルの裏取り
    conflicts = await management.get_unresolved_conflicts_logic()
    assert len(conflicts) > 0
    target = next(c for c in conflicts if c["entity"] == "ConflictNode")
    assert "Explicit contradiction" in target["reason"]

    # 4. 解決 (Approve)
    await management.resolve_conflict_logic(target["id"], action="approve")

    # 5. DB状態の最終検証
    async with await async_get_connection() as conn:
        async with conn.execute(
            "SELECT content FROM observations WHERE entity_name='ConflictNode' "
            "AND content='The sky is green.'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        async with conn.execute(
            "SELECT resolved FROM conflicts WHERE id=?", (target["id"],)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_log_agent_attribution(mock_llm):
    """
    Integration Test: 異なるエージェントIDでの保存が正しく監査ログに記録されるか。
    """
    await save_memory_core(
        entities=[{"name": "NodeA", "description": "Owner A"}], agent_id="agent_alpha"
    )

    await save_memory_core(
        entities=[{"name": "NodeB", "description": "Owner B"}], agent_id="agent_beta"
    )

    history = await management.get_audit_history_logic(limit=10)
    agent_ids = [h["agent"] for h in history]
    assert "agent_alpha" in agent_ids
    assert "agent_beta" in agent_ids


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dashboard_api_error_handling(mock_llm):
    """
    Integration Test: 存在しない衝突IDの解決を試みた際のエラーハンドリング。
    """
    # 存在しない ID (9999) を指定
    res = await management.resolve_conflict_logic(9999, action="approve")
    assert "Error" in res
    assert "not found" in res.lower()
