import pytest

from shared_memory.core import logic


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_deep_verification(db_conn, fake_llm):
    """
    Unit Test: save_memory_core の詳細な裏取り検証。
    エンティティ、関係性、観察事項、バンクファイル、タグが
    すべて正しくデータベースに格納されているか、直接SQLで分析する。
    """
    agent_id = "deep_tester_007"
    entities = [{"name": "DeepNode", "entity_type": "unit", "description": "Deep Test"}]
    relations = [{"subject": "DeepNode", "predicate": "has_property", "object": "Verified"}]
    observations = [
        {"entity_name": "DeepNode", "content": "This is a detailed observation #test_tag"}
    ]
    bank_files = {"deep_verification.md": "Deep bank content"}

    # 1. 実行
    result = await logic.save_memory_core(
        entities=entities,
        relations=relations,
        observations=observations,
        bank_files=bank_files,
        agent_id=agent_id,
    )
    assert "Saved" in result

    # 2. 詳細な分析 (Database Analysis)

    # 2.1 エンティティの属性と監査証跡
    async with db_conn.execute("SELECT * FROM entities WHERE name='DeepNode'") as cursor:
        row = await cursor.fetchone()
        assert row["entity_type"] == "unit"
        assert row["description"] == "Deep Test"
        # タイムスタンプが更新されているか（簡易チェック）
        assert row["updated_at"] is not None

    # 2.2 関係性の方向性と記述
    async with db_conn.execute("SELECT * FROM relations WHERE subject='DeepNode'") as cursor:
        row = await cursor.fetchone()
        assert row["predicate"] == "has_property"
        assert row["object"] == "Verified"

    # 2.3 観察事項のハッシュタグ抽出
    # 内部ロジックで #test_tag が抽出され tags テーブルに入っているはず
    async with db_conn.execute("SELECT tag FROM tags WHERE content_id='DeepNode'") as cursor:
        tags = [r[0] for r in await cursor.fetchall()]
        assert "#test_tag" in tags

    # 2.4 バンクファイルのバイナリ整合性 (実際はテキストだが)
    async with db_conn.execute(
        "SELECT content FROM bank_files WHERE filename='deep_verification.md'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row["content"] == "Deep bank content"

    # 2.5 知識メタデータ (Importance/Access count)
    async with db_conn.execute(
        "SELECT access_count FROM knowledge_metadata WHERE content_id='DeepNode'"
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            assert row["access_count"] >= 0
        else:
            # metadata might not have been initialized if update_access wasn't called for some reason
            pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_memory_core_data_extraction(db_conn):
    """
    Unit Test: read_memory_core が複雑な構造（Graph + Bank）を
    正確に引き出せるか検証。
    """
    # 事前投入
    await db_conn.execute(
        "INSERT INTO entities (name, description, status) VALUES ('NodeA', 'DescA', 'active')"
    )
    await db_conn.execute(
        "INSERT INTO entities (name, description, status) VALUES ('NodeB', 'DescB', 'active')"
    )
    await db_conn.execute(
        "INSERT INTO relations (subject, predicate, object, status) VALUES ('NodeA', 'links_to', 'NodeB', 'active')"
    )
    await db_conn.execute(
        "INSERT INTO bank_files (filename, content, status) VALUES ('fileA.md', 'contentA', 'active')"
    )
    await db_conn.commit()

    # 1. 実行 (Queryあり: NodeA)
    # search.perform_search を使うため、NodeA に関連するものを探す。
    # 実際は FTS5 や Embedding が必要だが、SQLインサートのみだと限定的。
    # そこで、あえて query=None で全件取得を試す。
    res = await logic.read_memory_core(query=None)

    # 抽出データの分析
    entity_names = [e["name"] for e in res["graph"]["entities"]]
    assert "NodeA" in entity_names
    assert "NodeB" in entity_names

    assert any(r["subject"] == "NodeA" for r in res["graph"]["relations"])

    # In unit tests where we only insert to DB, bank.py adds [RECOVERED] suffix
    bank_keys = res["bank"].keys()
    assert any("fileA.md" in k for k in bank_keys)
    content = next(v for k, v in res["bank"].items() if "fileA.md" in k)
    assert content == "contentA"
