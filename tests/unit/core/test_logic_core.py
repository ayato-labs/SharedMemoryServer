import pytest
from shared_memory.core import logic
from shared_memory.infra.database import async_get_connection

@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_memory_core_db_integrity(db_conn, fake_llm):
    """
    Unit Test: save_memory_core を実行し、データベースの各テーブルに
    意図したデータが『本当に』書き込まれているかを直接SQLで検証する。
    Mock (MagicMock) は不使用。FakeGeminiClient を使用。
    """
    entities = [
        {"name": "CoreNode", "description": "Core Logic Test", "entity_type": "test"}
    ]
    observations = [
        {"entity_name": "CoreNode", "content": "Observation for Core Logic"}
    ]
    bank_files = {"core_logic.md": "Bank file for core logic test"}
    agent_id = "logic_tester_001"

    # 1. 実行
    result = await logic.save_memory_core(
        entities=entities,
        observations=observations,
        bank_files=bank_files,
        agent_id=agent_id
    )
    assert "Saved" in result

    # 2. 裏取り (Direct SQL Verification)
    
    # 2.1 entities テーブル
    async with db_conn.execute("SELECT * FROM entities WHERE name='CoreNode'") as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["description"] == "Core Logic Test"
        assert row["updated_by"] == agent_id
        assert row["status"] == "active"

    # 2.2 observations テーブル
    async with db_conn.execute("SELECT * FROM observations WHERE entity_name='CoreNode'") as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["content"] == "Observation for Core Logic"
        assert row["created_by"] == agent_id

    # 2.3 bank_files テーブル
    async with db_conn.execute("SELECT * FROM bank_files WHERE filename='core_logic.md'") as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["content"] == "Bank file for core logic test"

    # 2.4 audit_logs テーブル (トレーサビリティ)
    async with db_conn.execute("SELECT action, table_name FROM audit_logs WHERE agent_id=?", (agent_id,)) as cursor:
        rows = await cursor.fetchall()
        tables = [r["table_name"] for r in rows]
        assert "entities" in tables
        assert "observations" in tables
        assert "bank_files" in tables

@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_memory_core_functional(db_conn):
    """
    Unit Test: read_memory_core がデータベースから正しくデータを引き出せるか検証。
    """
    # 事前データ投入
    await db_conn.execute(
        "INSERT INTO entities (name, description, status) VALUES (?, ?, ?)",
        ("ReadNode", "Read Test Description", "active")
    )
    await db_conn.execute(
        "INSERT INTO observations (entity_name, content, status) VALUES (?, ?, ?)",
        ("ReadNode", "Read Test Observation", "active")
    )
    await db_conn.commit()

    # 実行
    res = await logic.read_memory_core(query="ReadNode")
    
    assert isinstance(res, dict)
    graph = res["graph"]
    assert any(e["name"] == "ReadNode" for e in graph["entities"])
    assert any(o["entity"] == "ReadNode" for o in graph["observations"])
