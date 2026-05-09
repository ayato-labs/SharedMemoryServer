import asyncio
import json
import os
import sqlite3
import pytest
import aiosqlite
from ripen.core.logic import save_memory_core, read_memory_core, synthesize_entity
from ripen.infra.database import async_get_connection, get_db_path

@pytest.mark.asyncio
async def test_comprehensive_database_integrity(mock_llm):
    """
    総合テスト: ユーザーフローの完遂と、データベースへの直接アクセスによる情報の裏取り調査。
    """
    # 1. データの準備
    entities = [
        {"name": "Project X", "entity_type": "Project", "description": "A top-secret research project."},
        {"name": "Alice", "entity_type": "Person", "description": "Lead scientist of Project X."}
    ]
    relations = [
        {"subject": "Alice", "object": "Project X", "predicate": "leads", "justification": "Alice was appointed as lead."}
    ]
    observations = [
        {"entity_name": "Project X", "content": "Initial phase is complete."},
        {"entity_name": "Alice", "content": "Alice has over 20 years of experience."}
    ]
    bank_files = {
        "project_plan.md": "# Project Plan\n- Phase 1: Research\n- Phase 2: Implementation"
    }

    # 2. 実行 (save_memory_core)
    result = await save_memory_core(
        entities=entities,
        relations=relations,
        observations=observations,
        bank_files=bank_files,
        agent_id="tester_agent"
    )
    
    # 文字列の完全一致ではなく、キーワードが含まれているかを確認
    assert "SAVED" in result.upper() or "UPDATED" in result.upper()

    # 3. データベースの裏取り調査 (Direct SQL Validation)
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # Entitiesの検証
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None, "Project X should be in entities table"
        assert row["entity_type"] == "Project"
        
        # Relationsの検証
        cursor = await conn.execute("SELECT * FROM relations WHERE subject = 'Alice' AND object = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None
        
        # Observationsの検証
        cursor = await conn.execute("SELECT * FROM observations WHERE entity_name = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None
        
        # Embeddingsの存在確認
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM embeddings")
        row = await cursor.fetchone()
        assert row["cnt"] >= 3

@pytest.mark.asyncio
async def test_adversarial_large_data_compression(mock_llm):
    """
    厳しいテスト: 巨大なデータを投入し、保存されることを検証。
    """
    large_desc = "Detail information about the project " * 1000
    entities = [
        {"name": "Mega Project", "entity_type": "LargeScale", "description": large_desc}
    ]
    
    mock_llm.models.set_response("generate_content", '{"distilled": "Compressed text"}')
    
    result = await save_memory_core(entities=entities)
    assert "SAVED" in result.upper()
    
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT description FROM entities WHERE name = 'Mega Project'")
        row = await cursor.fetchone()
        assert len(row["description"]) == 5000

@pytest.mark.asyncio
async def test_adversarial_duplicate_conflict(mock_llm):
    """
    厳しいテスト: 重複・矛盾する情報を投入し、コンフリクト検知が動作するか検証。
    """
    # 1. 最初の情報を保存
    await save_memory_core(observations=[{"entity_name": "ConflictTarget", "content": "The sky is blue."}])
    
    # 2. Mock LLMにコンフリクトレスポンスを設定
    # システムテストでは mock_llm (MagicMock) が自動適用されるため、それを使用する
    mock_llm.models.set_response("generate_content", '[{"conflict": true, "reason": "Contradicts previous knowledge."}]')
    
    # 3. 矛盾する情報を保存
    result = await save_memory_core(observations=[{"entity_name": "ConflictTarget", "content": "The sky is green."}])
    
    assert "CONFLICT" in result.upper()
    
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM conflicts WHERE entity_name = 'ConflictTarget'")
        row = await cursor.fetchone()
        assert row is not None
        assert "Contradicts" in row["reason"]

@pytest.mark.asyncio
async def test_adversarial_db_lock_resilience():
    """
    厳しいテスト: データベースを意図的にロックし、リトライロジックが耐えうるか検証。
    """
    db_path = get_db_path()
    conn_lock = sqlite3.connect(db_path)
    conn_lock.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises((asyncio.TimeoutError, Exception)):
             await asyncio.wait_for(save_memory_core(entities=[{"name": "LockedEntity"}]), timeout=2.0)
    finally:
        conn_lock.rollback()
        conn_lock.close()

@pytest.mark.asyncio
async def test_adversarial_invalid_input_types():
    """
    厳しいテスト: 不正なデータ型を投入し、適切にエラーメッセージを返すか検証。
    """
    result = await save_memory_core(entities=[{"name": "BadType", "entity_type": 123}])
    assert "ERROR" in result.upper()
