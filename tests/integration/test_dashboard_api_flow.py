import pytest
import json
from shared_memory.core.logic import save_memory_core
from shared_memory.ops import management
from shared_memory.infra.database import async_get_connection

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_conflict_detection_and_resolution_flow(mock_llm):
    """
    Integration Test: 衝突検知からDashboard経由の解決、DB反映までの全フローを検証。
    """
    # 1. 初期データ準備
    await save_memory_core(
        entities=[{"name": "ConflictNode", "description": "Original description"}]
    )
    
    # 2. 衝突するデータの保存 (Mock LLM が conflict=True を返すように設定)
    # 内部で json.loads されるため、エスケープされたJSON文字列を返す
    mock_llm.models.set_response(
        "generate_content", 
        json.dumps([{"conflict": True, "reason": "Explicit contradiction detected by LLM"}])
    )
    
    # observations の保存
    result = await save_memory_core(
        observations=[{"entity_name": "ConflictNode", "content": "Contradicting observation"}]
    )
    assert "CONFLICTS DETECTED" in result
    
    # 3. 衝突テーブルの裏取り (management logic 経由)
    conflicts = await management.get_unresolved_conflicts_logic()
    assert len(conflicts) > 0
    target = next(c for c in conflicts if c["entity"] == "ConflictNode")
    assert "Explicit contradiction" in target["reason"]
    
    # 4. 解決 (Approve) - これにより observations テーブルへ正式に書き込まれる
    await management.resolve_conflict_logic(target["id"], action="approve")
    
    # 5. DB状態の最終検証 (裏取り)
    async with await async_get_connection() as conn:
        # 観察事項が追加されているか
        async with conn.execute(
            "SELECT content FROM observations WHERE entity_name='ConflictNode' AND content='Contradicting observation'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            
        # 衝突ステータスが解決済み(1)になっているか
        async with conn.execute(
            "SELECT resolved FROM conflicts WHERE id=?", (target["id"],)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1

@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_log_agent_attribution(mock_llm):
    """
    Integration Test: 異なるエージェントIDでの保存が正しく監査ログに記録されるか（マルチエージェント対応）。
    """
    # エージェントAによる保存
    await save_memory_core(
        entities=[{"name": "NodeA", "description": "Owner A"}], 
        agent_id="agent_alpha"
    )
    
    # エージェントBによる保存
    await save_memory_core(
        entities=[{"name": "NodeB", "description": "Owner B"}], 
        agent_id="agent_beta"
    )
    
    # 監査ログの検証
    history = await management.get_audit_history_logic(limit=10)
    
    # agent_id が正しく記録されているか
    agent_ids = [h["agent"] for h in history]
    assert "agent_alpha" in agent_ids
    assert "agent_beta" in agent_ids
    
    # 特定の操作が特定のエージェントに紐付いているか
    log_a = next(h for h in history if "NodeA" in str(h["cid"]))
    assert log_a["agent"] == "agent_alpha"

@pytest.mark.asyncio
@pytest.mark.integration
async def test_dashboard_api_error_handling(mock_llm):
    """
    Integration Test: 存在しない衝突IDの解決を試みた際のエラーハンドリング。
    """
    # 存在しない ID (9999) を指定
    with pytest.raises(Exception): # もしくは適切なエラーレスポンス
        await management.resolve_conflict_logic(9999, action="approve")
