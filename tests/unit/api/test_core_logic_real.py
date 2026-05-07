import pytest

from shared_memory.core.logic import read_memory_core, save_memory_core


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_real_db_verification(db_conn):
    """
    Unit Test: save_memory_core の実動作とDB裏取り。
    Mockを使用せず、正規化からDB保存、監査ログ記録までを一貫して検証。
    """
    # 1. テストデータ準備
    entities = [
        {"name": "UnitNode", "description": "Created during unit test", "entity_type": "unit_test"}
    ]
    observations = [{"entity_name": "UnitNode", "content": "Observing the unit test behavior"}]
    bank_files = {"unit_test.md": "Content for bank file verification"}

    # 2. ロジック実行 (Mockなし)
    # ※ LLMが未設定の場合は、内部で例外が発生するか、フォールバックが機能するはず
    result = await save_memory_core(
        entities=entities,
        observations=observations,
        bank_files=bank_files,
        agent_id="real_unit_tester",
    )

    assert "Saved" in result

    # 3. データベース直接検証 (裏取り)
    # 3.1 エンティティの存在確認
    async with db_conn.execute(
        "SELECT name, entity_type, description, status FROM entities WHERE name='UnitNode'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "UnitNode"
        assert row[1] == "unit_test"
        assert row[2] == "Created during unit test"
        assert row[3] == "active"

    # 3.2 観察事項の確認
    async with db_conn.execute(
        "SELECT entity_name, content FROM observations WHERE entity_name='UnitNode'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "UnitNode"
        assert row[1] == "Observing the unit test behavior"

    # 3.3 バンクファイルの確認
    async with db_conn.execute(
        "SELECT filename, content FROM bank_files WHERE filename='unit_test.md'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[1] == "Content for bank file verification"

    # 3.4 監査ログの確認 (トレーサビリティ)
    async with db_conn.execute(
        "SELECT table_name, action, agent_id FROM audit_logs WHERE agent_id='real_unit_tester'"
    ) as cursor:
        rows = await cursor.fetchall()
        assert len(rows) >= 3  # entities, observations, bank_files
        tables = [r[0] for r in rows]
        assert "entities" in tables
        assert "observations" in tables
        assert "bank_files" in tables


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_normalization_synonyms(db_conn):
    """
    Unit Test: 入力データの正規化（シノニム対応）の検証。
    """
    # 'title' -> 'name', 'desc' -> 'description' などのシノニム
    entities = [{"title": "SynonymNode", "desc": "Synonym description"}]
    # 'observation' -> 'content'
    observations = [{"entity": "SynonymNode", "observation": "Synonym content"}]

    await save_memory_core(entities=entities, observations=observations)

    async with db_conn.execute(
        "SELECT name, description FROM entities WHERE name='SynonymNode'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "SynonymNode"
        assert row[1] == "Synonym description"

    async with db_conn.execute(
        "SELECT content FROM observations WHERE entity_name='SynonymNode'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "Synonym content"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_memory_core_results_format(db_conn):
    """
    Unit Test: read_memory_core のレスポンス形式検証。
    """
    # データの事前投入
    await db_conn.execute(
        "INSERT INTO entities (name, description) VALUES ('ReadTest', 'Test read')"
    )
    await db_conn.commit()

    # 実行
    result = await read_memory_core(query="ReadTest")

    assert isinstance(result, dict)
    assert "graph" in result
    assert "bank" in result
    assert any(e["name"] == "ReadTest" for e in result["graph"]["entities"])
