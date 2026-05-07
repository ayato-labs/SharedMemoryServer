import pytest

from shared_memory.core import graph
from shared_memory.infra.database import async_get_connection


@pytest.mark.asyncio
@pytest.mark.unit
async def test_extract_hashtags_logic():
    """
    Unit Test: extract_hashtags_logic の挙動を確認。
    ストップワードの除外、頻度順の抽出が正しく行われること。
    """
    content = "Python is great. Python is powerful. Programming with Python and AI."
    tags = graph.extract_hashtags_logic(content)

    # Pythonが最頻出なので必ず含まれるはず
    assert "#python" in tags
    # Programming, Powerful などが含まれる可能性がある
    assert len(tags) <= 5
    # ストップワードが含まれていないこと
    assert "#is" not in tags
    assert "#and" not in tags


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_tags_success():
    """
    Unit Test: タグの保存と重複排除、更新を検証。
    """
    async with await async_get_connection() as conn:
        # 初回保存
        await graph.save_tags("NodeA", "entity", ["#tag1", "#tag2"], conn)

        # 裏取り
        async with conn.execute("SELECT tag FROM tags WHERE content_id='NodeA'") as cursor:
            rows = await cursor.fetchall()
            tags = [r[0] for r in rows]
            assert "#tag1" in tags
            assert "#tag2" in tags
            assert len(tags) == 2

        # 更新（古いタグは削除されるはず）
        await graph.save_tags("NodeA", "entity", ["#tag3"], conn)
        async with conn.execute("SELECT tag FROM tags WHERE content_id='NodeA'") as cursor:
            rows = await cursor.fetchall()
            tags = [r[0] for r in rows]
            assert "#tag3" in tags
            assert "#tag1" not in tags
            assert len(tags) == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_tags():
    """
    Unit Test: タグによる検索を検証。
    """
    async with await async_get_connection() as conn:
        await graph.save_tags("NodeX", "entity", ["#shared"], conn)
        await graph.save_tags("NodeY", "entity", ["#shared", "#exclusive"], conn)

        # #exclusive で検索 -> NodeY のみ
        results = await graph.search_by_tags(["#exclusive"], conn)
        assert results == ["NodeY"]

        # #shared で検索 -> NodeX, NodeY
        results = await graph.search_by_tags(["#shared"], conn)
        assert "NodeX" in results
        assert "NodeY" in results
        assert len(results) == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_entities_basic():
    """
    Unit Test: save_entities の基本保存機能を検証（単体レベル）。
    """
    entities = [{"name": "BasicNode", "description": "Basic Desc", "importance": 7}]
    async with await async_get_connection() as conn:
        # ベクトルはなしで保存
        msg = await graph.save_entities(entities, "test_agent", conn, precomputed_vectors=[None])
        assert "Saved 1 entities" in msg

        # 裏取り
        async with conn.execute("SELECT importance FROM entities WHERE name='BasicNode'") as cursor:
            row = await cursor.fetchone()
            assert row[0] == 7


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_relations_basic():
    """
    Unit Test: save_relations の基本保存機能を検証。
    """
    relations = [{"subject": "A", "predicate": "links_to", "object": "B"}]
    async with await async_get_connection() as conn:
        msg = await graph.save_relations(relations, "test_agent", conn)
        assert "Saved 1 relations" in msg

        async with conn.execute("SELECT predicate FROM relations WHERE subject='A'") as cursor:
            row = await cursor.fetchone()
            assert row[0] == "links_to"
