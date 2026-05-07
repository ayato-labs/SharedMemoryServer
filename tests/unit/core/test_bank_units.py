import os

import pytest

from shared_memory.common.utils import get_bank_dir
from shared_memory.core import bank
from shared_memory.infra.database import async_get_connection


@pytest.mark.asyncio
@pytest.mark.unit
async def test_initialize_bank():
    """
    Unit Test: バンクの初期化。指定されたデフォルトファイルが作成されること。
    """
    await bank.initialize_bank()
    bank_dir = get_bank_dir()

    # 少なくとも projectBrief.md は存在するはず
    path = os.path.join(bank_dir, "projectBrief.md")
    assert os.path.exists(path)

    with open(path, encoding="utf-8") as f:
        content = f.read()
        assert "# projectBrief.md" in content


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_bank_files_sync():
    """
    Unit Test: バンクファイルの保存（DBとディスクの同期）。
    """
    bank_files = {"unit_test_bank.md": "Bank Content"}
    async with await async_get_connection() as conn:
        msg = await bank.save_bank_files(bank_files, "test_agent", conn, precomputed_vectors=[None])
        assert "Updated 1 bank files" in msg

        # DB確認
        async with conn.execute(
            "SELECT content FROM bank_files WHERE filename='unit_test_bank.md'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "Bank Content"

        # ディスク確認
        bank_dir = get_bank_dir()
        path = os.path.join(bank_dir, "unit_test_bank.md")
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            assert f.read() == "Bank Content"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_bank_data():
    """
    Unit Test: バンクデータの読み取りと検索。
    """
    # 準備
    bank_files = {"search_me.md": "Specific Keyword Here"}
    async with await async_get_connection() as conn:
        await bank.save_bank_files(bank_files, "test_agent", conn, precomputed_vectors=[None])
        await conn.commit()

    # 全件読み取り
    data = await bank.read_bank_data()
    assert "search_me.md" in data

    # キーワード検索
    data_filtered = await bank.read_bank_data(query="Keyword")
    assert "search_me.md" in data_filtered

    data_none = await bank.read_bank_data(query="NonExistent")
    assert "search_me.md" not in data_none


@pytest.mark.asyncio
@pytest.mark.unit
async def test_repair_memory_logic():
    """
    Unit Test: DBからディスクへの復旧機能を検証。
    """
    bank_files = {"broken_disk.md": "Database is safe"}
    async with await async_get_connection() as conn:
        await bank.save_bank_files(bank_files, "test_agent", conn, precomputed_vectors=[None])
        await conn.commit()

    # ディスクのファイルを削除して擬似的に破損させる
    bank_dir = get_bank_dir()
    path = os.path.join(bank_dir, "broken_disk.md")
    if os.path.exists(path):
        os.remove(path)

    # 復旧実行
    result = await bank.repair_memory_logic()
    assert "Restored" in result

    # ディスクに復活しているか確認
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        assert f.read() == "Database is safe"
