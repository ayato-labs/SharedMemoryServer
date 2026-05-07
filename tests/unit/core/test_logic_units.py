from unittest.mock import AsyncMock, patch

import pytest

from shared_memory.core import logic
from shared_memory.infra.database import async_get_connection


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_full_success(fake_llm):
    """
    Unit Test: 正常系の保存フローを検証。
    エンティティ、関係、観察、バンクファイルが全て正しくDBに保存されること。
    """
    entities = [{"name": "UnitNode", "description": "Unit test node"}]
    relations = [{"subject": "UnitNode", "predicate": "tested_by", "object": "Pytest"}]
    observations = [{"entity_name": "UnitNode", "content": "Unit test observation"}]
    bank_files = {"test.md": "Unit test bank content"}

    result = await logic.save_memory_core(
        entities=entities,
        relations=relations,
        observations=observations,
        bank_files=bank_files,
    )

    assert "Saved 1 entities" in result
    assert "Saved 1 relations" in result
    assert "Saved 1 observations" in result
    assert "Updated 1 bank files" in result

    # DBの裏取り
    async with await async_get_connection() as conn:
        # Entities
        async with conn.execute(
            "SELECT name, description FROM entities WHERE name='UnitNode'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[1] == "Unit test node"

        # Observations
        async with conn.execute(
            "SELECT content FROM observations WHERE entity_name='UnitNode'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "Unit test observation"

        # Bank Files
        async with conn.execute(
            "SELECT content FROM bank_files WHERE filename='test.md'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "Unit test bank content"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_with_conflict(fake_llm):
    """
    Unit Test: LLMがコンフリクトを返した場合の挙動。
    """
    # 既存データの準備
    await logic.save_memory_core(entities=[{"name": "ConflictNode", "description": "Existing"}])

    # 観察のみを保存しようとする。
    # Phase 2.1 の graph.check_conflict をパッチしてコンフリクトを返させる。
    with patch("shared_memory.core.graph.check_conflict", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = [(True, "Already known")]

        observations = [{"entity_name": "ConflictNode", "content": "Duplicate info"}]
        result = await logic.save_memory_core(observations=observations)

        # Debug print
        print(f"DEBUG conflict: result='{result}'")

        assert "CONFLICTS DETECTED" in result
        assert "Saved 0 observations" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_empty_input(fake_llm):
    """
    Unit Test: 空の入力に対する堅牢性。
    エラーにならず、空の成功メッセージを返すこと。
    """
    result = await logic.save_memory_core(entities=[], observations=[], bank_files={})
    assert result == ""


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_ai_error_handling(fake_llm):
    """
    Unit Test: AI計算（埋め込み）でエラーが発生した場合のハンドリング。
    """
    # フェーズ 1.3 の asyncio.gather 内で呼ばれる compute_embeddings_bulk をパッチしてエラーにする。
    with patch(
        "shared_memory.core.logic.compute_embeddings_bulk",
        side_effect=Exception("AI Quota Exceeded"),
    ):
        entities = [{"name": "ErrorNode", "description": "Should fail"}]
        result = await logic.save_memory_core(entities=entities)

        # Debug print
        print(f"DEBUG ai_error: result='{result}'")

        assert "AI Error" in result

    # DBに保存されていないことを確認
    async with await async_get_connection() as conn:
        async with conn.execute("SELECT COUNT(*) FROM entities WHERE name='ErrorNode'") as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0
