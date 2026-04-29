import pytest

from shared_memory.core import logic
from shared_memory.infra.database import init_db


@pytest.mark.asyncio
async def test_full_save_pipeline(mock_llm):
    """
    結合テスト: Logic -> Embedding -> Graph -> DB の一連の流れを検証。
    LLM (Gemini) は MagicMock で制御。
    """
    await init_db(force=True)

    # 1. データの準備
    entities = [{"name": "IntegrationNode", "description": "Testing full flow"}]
    observations = [{"entity_name": "IntegrationNode", "content": "Integration test fact"}]

    # 2. 実行 (Logicが内部で各モジュールを呼び出す)
    # mock_llm は conftest.py で既に get_gemini_client にパッチされている想定
    result = await logic.save_memory_core(entities=entities, observations=observations)

    # 3. 検証: メッセージ
    assert "Saved 1 entities" in result
    assert "Saved 1 observations" in result

    # 4. 検証: DB状態
    from shared_memory.core.graph import get_graph_data

    saved_entities_data = await get_graph_data(query="IntegrationNode")
    assert "entities" in saved_entities_data
    assert len(saved_entities_data["entities"]) >= 1
    assert saved_entities_data["entities"][0]["name"] == "IntegrationNode"

    # ObservationがDBにあるか
    from shared_memory.infra.database import async_get_connection

    conn = await async_get_connection()
    async with conn.execute("SELECT content FROM observations") as cursor:
        rows = await cursor.fetchall()
        assert any("Integration test fact" in r[0] for r in rows)


@pytest.mark.asyncio
async def test_save_pipeline_with_llm_conflict_response(mock_llm):
    """
    結合テスト: LLMがコンフリクト（重複）を返した場合のパイプライン挙動。
    """
    await init_db(force=True)

    # LLMがコンフリクトを返すように設定
    mock_llm.models.set_response(
        "generate_content", '{"conflict": true, "reason": "Redundant data"}'
    )

    entities = [{"name": "DuplicateNode", "description": "I already exist"}]
    # Observations are where conflicts are checked
    obs = [{"entity_name": "DuplicateNode", "content": "Redundant fact"}]
    result = await logic.save_memory_core(entities=entities, observations=obs)

    assert "CONFLICTS DETECTED" in result
    assert "Saved 0 observations" in result
