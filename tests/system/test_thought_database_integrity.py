import asyncio
import os
import sqlite3
import pytest
import aiosqlite
from ripen.core.thought_logic import process_thought_core, init_thoughts_db, get_thought_history
from ripen.common.utils import get_thoughts_db_path

@pytest.mark.asyncio
async def test_thought_persistence_integrity():
    """
    総合テスト: 思考履歴の永続化とFTS5インデックスの裏取り調査。
    """
    session_id = "integrity_session_123"
    
    # 1. 思考のプロセス
    await process_thought_core(
        thought="I am researching the impact of solar flares on satellite communication.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_id
    )
    
    await process_thought_core(
        thought="The data suggests X-class flares are the most disruptive.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id=session_id
    )

    # 2. データベースの裏取り (Direct SQL)
    db_path = get_thoughts_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 履歴テーブルの検証
        cursor = await conn.execute(
            "SELECT * FROM thought_history WHERE session_id = ? ORDER BY thought_number ASC",
            (session_id,)
        )
        rows = await cursor.fetchall()
        assert len(rows) == 2
        assert "solar flares" in rows[0]["thought"]
        assert "X-class" in rows[1]["thought"]
        assert rows[0]["next_thought_needed"] == 1
        assert rows[1]["next_thought_needed"] == 0
        
        # FTS5インデックスの検証 (情報の裏取り)
        cursor = await conn.execute(
            "SELECT * FROM thought_history_fts WHERE thought_history_fts MATCH 'satellite'",
        )
        row = await cursor.fetchone()
        assert row is not None, "FTS5 index should contain 'satellite'"
        assert row["session_id"] == session_id

@pytest.mark.asyncio
async def test_adversarial_thought_sequence_conflicts():
    """
    厳しいテスト: 不正なシーケンスや重複番号の投入に対する耐性を検証。
    """
    session_id = "adversarial_session"
    
    # 正常な投入
    await process_thought_core(thought="Base", thought_number=1, total_thoughts=5, next_thought_needed=True, session_id=session_id)
    
    # 重複する思考番号の投入 (ERRORを期待)
    result = await process_thought_core(thought="Duplicate", thought_number=1, total_thoughts=5, next_thought_needed=True, session_id=session_id)
    assert "error" in result
    assert "Duplicate thought number" in result["error"]
    
    # 不正なリビジョン (存在しない番号を指定)
    result = await process_thought_core(
        thought="Revision", 
        thought_number=2, 
        total_thoughts=5, 
        next_thought_needed=True, 
        is_revision=True, 
        revises_thought=99, 
        session_id=session_id
    )
    assert "error" in result
    assert "does not exist" in result["error"]

@pytest.mark.asyncio
async def test_thought_session_isolation():
    """
    厳しいテスト: セッション間の隔離性が保たれているか検証。
    """
    await process_thought_core(thought="Secret A", thought_number=1, total_thoughts=1, next_thought_needed=False, session_id="session_A")
    await process_thought_core(thought="Secret B", thought_number=1, total_thoughts=1, next_thought_needed=False, session_id="session_B")
    
    history_a = await get_thought_history("session_A")
    history_b = await get_thought_history("session_B")
    
    assert len(history_a) == 1
    assert "Secret A" in history_a[0]["thought"]
    assert "Secret B" not in str(history_a)
    
    assert len(history_b) == 1
    assert "Secret B" in history_b[0]["thought"]
    assert "Secret A" not in str(history_b)
