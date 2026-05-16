import pytest

from ripen.core.logic import normalize_entities, save_memory_core
from ripen.infra.database import async_get_connection


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_memory_core_no_mocks(fake_llm):
    """
    単体テスト: Mockを使用せず、Fake implementationを使用して
    すべてのデータ型 (エンティティ、関係、観察、バンク) の保存とDB裏取りを行う。
    """
    # 1. 準備
    entities = [{"name": "UnitNode", "description": "Unit desc"}]
    relations = [{"subject": "UnitNode", "object": "Other", "predicate": "related"}]
    observations = [{"entity_name": "UnitNode", "content": "Unit fact"}]
    bank_files = {"unit.md": "Unit content"}

    # 2. 実行
    result = await save_memory_core(
        entities=entities,
        relations=relations,
        observations=observations,
        bank_files=bank_files,
        agent_id="unmocked_tester",
    )

    assert "SAVED" in result.upper()

    # 3. データベースの裏取り (Direct SQL)
    async with await async_get_connection() as conn:
        # Entities
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'UnitNode'")
        assert await cursor.fetchone() is not None

        # Relations
        cursor = await conn.execute("SELECT * FROM relations WHERE subject = 'UnitNode'")
        assert await cursor.fetchone() is not None

        # Observations
        cursor = await conn.execute("SELECT * FROM observations WHERE entity_name = 'UnitNode'")
        assert await cursor.fetchone() is not None

        # Bank Files
        cursor = await conn.execute("SELECT * FROM bank_files WHERE filename = 'unit.md'")
        assert await cursor.fetchone() is not None

        # Audit Logs (トレーサビリティの裏取り)
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE agent_id = 'unmocked_tester'"
        )
        count = (await cursor.fetchone())[0]
        assert count >= 3


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
