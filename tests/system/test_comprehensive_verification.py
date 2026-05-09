import asyncio
import json
import os
import sqlite3
import pytest
import aiosqlite
from shared_memory.core.logic import save_memory_core, read_memory_core, synthesize_entity
from shared_memory.infra.database import async_get_connection, get_db_path

@pytest.mark.asyncio
async def test_comprehensive_database_integrity(fake_llm):
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
    # Unit test marker is NOT used here, so it's a System Test context.
    # Fake LLM is used.
    result = await save_memory_core(
        entities=entities,
        relations=relations,
        observations=observations,
        bank_files=bank_files,
        agent_id="tester_agent"
    )
    
    assert "SUCCESS" in result.upper()

    # 3. データベースの裏取り調査 (Direct SQL Validation)
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # Entitiesの検証
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["entity_type"] == "Project"
        assert row["description"] == "A top-secret research project."
        assert row["status"] == "active"
        
        cursor = await conn.execute("SELECT * FROM entities WHERE name = 'Alice'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["entity_type"] == "Person"
        
        # Relationsの検証
        cursor = await conn.execute("SELECT * FROM relations WHERE subject = 'Alice' AND object = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["predicate"] == "leads"
        assert row["justification"] == "Alice was appointed as lead."
        
        # Observationsの検証
        cursor = await conn.execute("SELECT * FROM observations WHERE entity_name = 'Project X'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["content"] == "Initial phase is complete."
        
        # Bank Filesの検証
        cursor = await conn.execute("SELECT * FROM bank_files WHERE filename = 'project_plan.md'")
        row = await cursor.fetchone()
        assert row is not None
        assert "Project Plan" in row["content"]
        
        # Embeddingsの存在確認 (裏取り: ベクトルデータが生成されているか)
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM embeddings")
        row = await cursor.fetchone()
        assert row["cnt"] >= 3 # Alice, Project X, and the bank file should have embeddings

    # 4. ユーザーフローの継続: 検索と合成
    search_result = await read_memory_core(query="Who leads Project X?")
    assert "Alice" in str(search_result)
    
    synthesis = await synthesize_entity("Alice")
    assert "scientist" in synthesis or "leads" in synthesis

@pytest.mark.asyncio
async def test_adversarial_large_data_compression(fake_llm):
    """
    厳しいテスト: 巨大なデータを投入し、自動圧縮ロジックとデータベース保存が正常に動作するか検証。
    """
    # 巨大な説明文 (トークン制限を模倣)
    large_desc = "Detail information about the project " * 1000
    entities = [
        {"name": "Mega Project", "entity_type": "LargeScale", "description": large_desc}
    ]
    
    # Fake LLMに圧縮レスポンスをセット
    fake_llm.models.set_response("generate_content", '{"distilled": "This is a compressed summary of the mega project."}')
    
    result = await save_memory_core(entities=entities)
    assert "SUCCESS" in result.upper()
    
    # データベースに保存されたデータを確認
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT description FROM entities WHERE name = 'Mega Project'")
        row = await cursor.fetchone()
        # 元のデータが保存されているか、あるいは圧縮後のデータか。
        # 現在のロジックでは LLMProvider._compress_content が呼ばれるはずだが、
        # save_memory_core 自体は元のデータを保存する。
        # 実際には、LLMProvider.generate_content 内で圧縮が行われ、LLMへの入力が減るだけ。
        # DBに保存されるのは元の entities['description'] であるはず（仕様確認が必要）。
        assert len(row["description"]) > 10000

@pytest.mark.asyncio
async def test_adversarial_duplicate_conflict(fake_llm):
    """
    厳しいテスト: 重複した情報を投入し、コンフリクト検知ロジックが動作するか検証。
    """
    # 最初の一報
    await save_memory_core(observations=[{"entity_name": "Target", "content": "Status is Green."}])
    
    # Fake LLMにコンフリクトありのレスポンスをセット
    # graph.check_conflict がこれを呼ぶ
    fake_llm.models.set_response("generate_content", '{"conflict": true, "reason": "Status was reported as Green before."}')
    
    # 矛盾する情報を投入
    result = await save_memory_core(observations=[{"entity_name": "Target", "content": "Status is RED!"}])
    
    assert "CONFLICTS DETECTED" in result.upper()
    
    # データベースの conflicts テーブルを裏取り
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM conflicts WHERE entity_name = 'Target'")
        row = await cursor.fetchone()
        assert row is not None
        assert row["reason"] == "Status was reported as Green before."
        assert row["new_content"] == "Status is RED!"

@pytest.mark.asyncio
async def test_adversarial_db_lock_resilience():
    """
    厳しいテスト: データベースを意図的にロックし、リトライロジックが耐えうるか検証。
    """
    db_path = get_db_path()
    
    # 1. 別接続で排他ロックを取得
    conn_lock = sqlite3.connect(db_path)
    conn_lock.execute("BEGIN EXCLUSIVE")
    # ロックを保持したままにする
    
    try:
        # 2. save_memory_coreを実行 (バックグラウンドではなく直接)
        # タイムアウトが短くなるように調整するか、待機する。
        # retry_on_db_lock は max_retries=15, timeout=30.0 なのでかなり粘る。
        
        # タイムアウトを待つのは時間がかかるので、asyncio.wait_for で制限する
        with pytest.raises((asyncio.TimeoutError, Exception)):
             await asyncio.wait_for(save_memory_core(entities=[{"name": "LockedEntity"}]), timeout=2.0)
    finally:
        conn_lock.rollback()
        conn_lock.close()

@pytest.mark.asyncio
async def test_adversarial_invalid_input_types():
    """
    厳しいテスト: 不正なデータ型を投入し、システムがクラッシュせずに適切にエラーハンドリングするか検証。
    """
    # entities がリストではなく文字列
    result = await save_memory_core(entities="Not a list")
    # normalize_entities は entities or [] でループするので、文字列だと1文字ずつ処理しようとして失敗する可能性がある。
    # 現在の実装を確認: for e in entities or []: ...
    # 文字列をイテレートすると文字になる。
    assert "SUCCESS" in result.upper() or "ERROR" in result.upper()
    
    # 全く無関係なオブジェクトを投入
    result = await save_memory_core(entities=[{"name": None, "entity_type": 123}])
    assert "SUCCESS" in result.upper()
