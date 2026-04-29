import pytest
import asyncio
import sqlite3
import aiosqlite
from unittest.mock import AsyncMock, patch
from shared_memory.infra.database import retry_on_db_lock

@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_on_db_lock_resilience():
    """DBロックエラーが発生した場合のリトライと最終的な成功をテスト"""
    
    call_count = 0
    
    @retry_on_db_lock(max_retries=5, initial_delay=0.01)
    async def dummy_db_call():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # retry_on_db_lock がキャッチする例外を直接投げる
            raise sqlite3.OperationalError("database is locked")
        return "success"

    # テスト高速化のために sleep を無効化
    with patch("shared_memory.infra.database.asyncio.sleep", return_value=None):
        result = await dummy_db_call()
        
    assert result == "success"
    assert call_count == 3

@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_quota_exhaustion_rotation():
    """AI APIのクォータ切れ(429)が発生した場合のモデルローテーションテスト"""
    from shared_memory.core.ai_control import retry_on_ai_quota
    
    call_count = 0
    
    @retry_on_ai_quota(max_retries=1, initial_backoff=0.01, rotate_models=True)
    async def failing_ai_call():
        nonlocal call_count
        call_count += 1
        raise Exception("429 Resource has been exhausted")

    with patch("shared_memory.core.ai_control.asyncio.sleep", return_value=None):
        with pytest.raises(Exception) as excinfo:
            await failing_ai_call()
        
        assert "429" in str(excinfo.value)
        assert call_count >= 2
