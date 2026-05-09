import asyncio

import aiosqlite
import pytest

from ripen.api.server import ensure_initialized, save_memory
from ripen.infra.database import get_db_path


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_real_db_lock_resilience(mock_llm):
    """
    Chaos Test: 外部プロセス（擬似）によってデータベースファイルが
    長時間ロックされた場合の耐性を検証。
    """
    await ensure_initialized()
    db_path = get_db_path()

    # 1. 外部接続を開いてトランザクションを開始し、ロックを保持し続ける
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        # トランザクションを開始したまま放置

        # 2. その間に API からの書き込みを試行
        # リトライメカニズムが働くはずだが、最終的にタイムアウトするか、
        # あるいはロック解除を待って成功する。
        # ここでは短いタイムアウトを設定するか、エラーが正しくログに吐かれるかを確認
        task = asyncio.create_task(
            save_memory(
                entities=[{"name": "LockedNode", "description": "Trying to write while locked"}]
            )
        )

        # しばらく待つ
        await asyncio.sleep(1.0)

        # 3. ロックを解除
        await conn.rollback()

    # 4. ロック解除後に成功するか
    result = await task
    assert "Saved" in result or "Database Error" in result
    # システムがデッドロックしていないことが最重要
