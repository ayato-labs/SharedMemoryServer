import pytest

from ripen.core.logic import (
    admin_run_knowledge_gc_core,
    list_inactive_knowledge_core,
    manage_knowledge_activation_core,
    save_memory_core,
)
from ripen.infra.database import async_get_connection


@pytest.mark.asyncio
async def test_knowledge_lifecycle_management_integrity(mock_llm):
    """
    総合テスト: 知識の有効化/無効化と、ガベージコレクションの裏取り調査。
    """
    # 1. データの準備 (保存)
    await save_memory_core(
        entities=[
            {"name": "OldKnowledge", "description": "This is very old."},
            {"name": "ActiveKnowledge", "description": "This is active."},
        ]
    )

    # 2. 知識の無効化 (manage_knowledge_activation_core)
    await manage_knowledge_activation_core(ids=["OldKnowledge"], status="inactive")

    # 裏取り調査 (DB)
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'OldKnowledge'")
        row = await cursor.fetchone()
        assert row[0] == "inactive"

        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'ActiveKnowledge'")
        row = await cursor.fetchone()
        assert row[0] == "active"

    # 3. 無効化された知識のリスト取得
    inactive_data = await list_inactive_knowledge_core()
    inactive_entities = inactive_data.get("entities", [])
    inactive_names = [e["name"] for e in inactive_entities]
    assert "OldKnowledge" in inactive_names
    assert "ActiveKnowledge" not in inactive_names

    # 4. ガベージコレクション (admin_run_knowledge_gc_core)
    # run_knowledge_gc_logic は「アクティブだが長期間アクセスされていない知識」を inactive に変える。

    # 既存のデータを「非常に古い (作成から時間が経過し、アクセスもない)」状態に更新
    async with await async_get_connection() as conn:
        sql = (
            "UPDATE entities SET created_at = datetime('now', '-200 days') "
            "WHERE name = 'ActiveKnowledge'"
        )
        await conn.execute(sql)
        await conn.commit()

    # GC実行
    gc_result = await admin_run_knowledge_gc_core(age_days=180, dry_run=False)
    assert "GC Complete" in gc_result or "Success" in gc_result

    # 裏取り調査: ActiveKnowledge が inactive になったか
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT status FROM entities WHERE name = 'ActiveKnowledge'")
        row = await cursor.fetchone()
        assert row[0] == "inactive", "ActiveKnowledge should be moved to inactive by GC"


@pytest.mark.asyncio
async def test_adversarial_gc_dry_run():
    """
    厳しいテスト: Dry Run時にデータが削除されないことを検証。
    """
    await save_memory_core(entities=[{"name": "DryRunTarget", "description": "Should stay."}])
    await manage_knowledge_activation_core(ids=["DryRunTarget"], status="inactive")

    async with await async_get_connection() as conn:
        sql = (
            "UPDATE entities SET updated_at = datetime('now', '-365 days') "
            "WHERE name = 'DryRunTarget'"
        )
        await conn.execute(sql)
        await conn.commit()

    # Dry Run 実行
    await admin_run_knowledge_gc_core(age_days=30, dry_run=True)

    # 裏取り調査: 消えていないことを確認
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM entities WHERE name = 'DryRunTarget'")
        count = (await cursor.fetchone())[0]
        assert count == 1, "DryRunTarget should NOT be purged during dry run"
