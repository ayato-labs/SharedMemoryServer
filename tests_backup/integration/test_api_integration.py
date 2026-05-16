import pytest

from ripen.core import logic, search
from ripen.infra.database import async_get_connection
from ripen.ops import management


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_and_hybrid_search_flow(mock_llm):
    """
    Integration Test: 保存からハイブリッド検索、知識合成までの一連のフローを検証。
    """
    # 1. 保存
    entities = [{"name": "IntegrationNode", "description": "Part of a larger system"}]
    observations = [{"entity_name": "IntegrationNode", "content": "Integration testing is crucial"}]
    bank_files = {"integration.md": "Bank file content for integration"}

    await logic.save_memory_core(
        entities=entities, observations=observations, bank_files=bank_files
    )

    # 2. 検索 (キーワード + セマンティック)
    # perform_search を呼び出し、期待したエンティティやファイルが返るか確認
    graph_data, bank_data = await search.perform_search("Integration")

    # エンティティが見つかっているか
    entity_names = [e["name"] for e in graph_data["entities"]]
    assert "IntegrationNode" in entity_names

    # 観察が含まれているか
    obs_contents = [o["content"] for o in graph_data["observations"]]
    assert "Integration testing is crucial" in obs_contents

    # バンクファイルが含まれているか
    assert "integration.md" in bank_data

    # 3. 知識合成
    mock_llm.models.set_response(
        "generate_content", "This is a synthesized summary of IntegrationNode."
    )

    summary = await search.synthesize_knowledge("IntegrationNode")
    assert "synthesized summary" in summary.lower()

    # 4. 監査ログの検証 (裏取り)
    # entities と bank_files の保存が監査ログに記録されているか
    audit_logs = await management.get_audit_history_logic(limit=10)
    tables_in_audit = [log["table"] for log in audit_logs]
    assert "entities" in tables_in_audit
    assert "bank_files" in tables_in_audit


@pytest.mark.asyncio
@pytest.mark.integration
async def test_conflict_and_recovery_flow(mock_llm):
    """
    Integration Test: 衝突検知と解決フローを検証。
    """
    # 1. 初期データ保存 (観察事項を1つ入れておく)
    await logic.save_memory_core(
        entities=[{"name": "StableNode", "description": "Immutable fact"}],
        observations=[{"entity_name": "StableNode", "content": "Original state"}],
    )

    # 2. 衝突するデータの保存試行
    # JSONリスト形式のレスポンスをシミュレート
    mock_llm.models.set_response(
        "generate_content", '[{"conflict": true, "reason": "Direct contradiction"}]'
    )

    result = await logic.save_memory_core(
        observations=[{"entity_name": "StableNode", "content": "Contradicting info"}]
    )
    assert "CONFLICTS DETECTED" in result

    # 3. 未解決の衝突リスト取得
    conflicts = await management.get_unresolved_conflicts_logic()
    assert len(conflicts) > 0
    target_conflict = next(c for c in conflicts if c["entity"] == "StableNode")
    assert "contradiction" in target_conflict["reason"].lower()

    # 4. 衝突の解決 (Approve)
    # これにより observations に追加されるはず
    await management.resolve_conflict_logic(target_conflict["id"], action="approve")

    # 5. 解決後の確認 (裏取り)
    async with await async_get_connection() as conn:
        # observations に追加されているか
        async with conn.execute(
            "SELECT content FROM observations WHERE entity_name='StableNode' "
            "AND content='Contradicting info'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        # 衝突が解決済みになっているか
        async with conn.execute(
            "SELECT resolved FROM conflicts WHERE id=?", (target_conflict["id"],)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1
