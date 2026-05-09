import pytest
from shared_memory.core.logic import save_memory_core, normalize_entities
from shared_memory.infra.database import async_get_connection

@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_memory_core_no_mocks(fake_llm):
    """
    単体テスト: Mock(MagicMock)を使用せず、Fake implementationを使用して
    save_memory_coreの基本的な保存動作を検証する。
    """
    # 準備
    entities = [{"name": "UnitEntity", "entity_type": "Unit", "description": "Unit test description"}]
    
    # 実行
    result = await save_memory_core(entities=entities)
    
    # 修正: 文字列が含まれているかを確認
    assert "SAVED" in result.upper()
    
    # データベースの裏取り
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'UnitEntity'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["entity_type"] == "Unit"

@pytest.mark.unit
def test_normalize_entities_pure():
    """
    単体テスト: 純粋な関数としてのnormalize_entitiesを検証。
    """
    raw = ["SimpleString", {"name": "DictName", "type": "Synonym"}]
    normalized = normalize_entities(raw)
    
    assert len(normalized) == 2
    assert normalized[0]["name"] == "SimpleString"
    assert normalized[0]["entity_type"] == "concept"
    assert normalized[1]["name"] == "DictName"
    assert normalized[1]["entity_type"] == "Synonym"
