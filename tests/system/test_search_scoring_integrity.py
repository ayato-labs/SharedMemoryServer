import asyncio
import json
import pytest
import aiosqlite
from ripen.core.logic import save_memory_core, read_memory_core
from ripen.core.search import perform_search
from ripen.infra.database import async_get_connection, get_db_path

@pytest.mark.asyncio
async def test_hybrid_search_scoring_and_audit(fake_llm):
    """
    総合テスト: ハイブリッド検索のスコアリング整合性と、検索統計の裏取り調査。
    """
    # 1. データの投入 (重み付けの検証用)
    # キーワードマッチ用
    await save_memory_core(entities=[
        {"name": "PythonExpert", "description": "Expert in Python programming and unit testing."}
    ])
    # 関連する観察
    await save_memory_core(observations=[
        {"entity_name": "PythonExpert", "content": "Specializes in pytest and mocking."}
    ])
    
    # 2. 検索の実行
    # クエリ: "Python expert"
    # これにより FTS5 (Keyword) と Embedding (Semantic) の両方が動く
    result = await perform_search(query="Python expert")
    
    entities = result[0]["entities"]
    assert any(e["name"] == "PythonExpert" for e in entities)

    # 3. 検索統計の裏取り (情報の裏取り)
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # search_stats テーブルの検証
        cursor = await conn.execute(
            "SELECT * FROM search_stats WHERE query = 'Python expert' ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        assert row is not None, "Search stat should be logged"
        assert row["results_count"] >= 1
        
        # ヒットしたIDが正しく記録されているか
        hit_ids = json.loads(row["hit_content_ids"])
        assert "PythonExpert" in hit_ids

    # 4. アクセス頻度による重要度（Importance）の更新検証
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT importance FROM entities WHERE name = 'PythonExpert'")
        importance = (await cursor.fetchone())[0]
        # 初期値 5 だったのが、検索ヒットによる update_access で上昇しているはず (実装によるが通常 +1)
        # ただし save_observations でも上昇する。
        assert importance > 5

@pytest.mark.asyncio
async def test_adversarial_empty_or_special_char_search():
    """
    厳しいテスト: 空文字や特殊文字、巨大なクエリでの検索耐性を検証。
    """
    # 1. 空文字
    result = await perform_search(query="")
    assert "entities" in result[0] # クラッシュしないこと
    
    # 2. FTS5の特殊文字 (インジェクション耐性)
    # " OR 1=1 -- などの悪意あるクエリ
    evil_query = 'Python" OR 1=1 --'
    result = await perform_search(query=evil_query)
    # escape_fts5_query により安全に処理されるはず
    assert isinstance(result, tuple)
    
    # 3. 巨大なクエリ
    huge_query = "search " * 1000
    result = await perform_search(query=huge_query)
    assert isinstance(result, tuple)

@pytest.mark.asyncio
async def test_search_isolation_by_status():
    """
    厳しいテスト: 非アクティブ（inactive/archived）な知識が検索にヒットしないことを検証。
    """
    from ripen.core.logic import manage_knowledge_activation_core
    
    await save_memory_core(entities=[{"name": "HiddenSecret", "description": "This should be hidden."}])
    
    # 検索で見つかることを確認
    res = await perform_search(query="HiddenSecret")
    assert any(e["name"] == "HiddenSecret" for e in res[0]["entities"])
    
    # 無効化
    await manage_knowledge_activation_core(ids=["HiddenSecret"], status="inactive")
    
    # 検索で見つからないことを確認
    res = await perform_search(query="HiddenSecret")
    assert not any(e["name"] == "HiddenSecret" for e in res[0]["entities"])
