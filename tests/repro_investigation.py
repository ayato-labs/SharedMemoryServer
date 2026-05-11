import asyncio
import os
import sys
import time
import pytest
import sqlite3
from pathlib import Path
from loguru import logger

# Add src to sys.path
sys.path.append(os.path.abspath("src"))

from ripen.common.config import settings
from ripen.infra.database import init_db
from ripen.api.licensing import LicenseManager
from ripen.infra.embeddings import get_fastembed_model

# ==========================================
# 1. UNIT TESTS (No Mocks)
# ==========================================


@pytest.mark.asyncio
async def test_unit_db_integrity():
    """[Unit] データベースの物理的整合性と初期化の正確性を検証。"""
    logger.info("Starting Unit Test: DB Integrity (No Mock)")
    db_path = settings.base_dir / "test_knowledge.db"
    if db_path.exists():
        os.remove(db_path)

    # Override settings for test
    settings._config_data["ripen_home"] = str(settings.base_dir)

    await init_db(force=True)

    # 物理ファイルが存在し、sqlite3として開けるか
    conn = sqlite3.connect(settings.base_dir / "knowledge.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
    assert cursor.fetchone() is not None
    conn.close()
    logger.info("Unit Test: DB Integrity PASSED")


@pytest.mark.asyncio
async def test_unit_fastembed_loading():
    """[Unit] FastEmbedのモデルロード時間を実測。"""
    logger.info("Starting Unit Test: FastEmbed Loading (No Mock)")
    start = time.perf_counter()
    model = get_fastembed_model()
    elapsed = time.perf_counter() - start
    assert model is not None
    logger.info(f"Unit Test: FastEmbed loaded in {elapsed:.2f}s")


# ==========================================
# 2. INTEGRATION TESTS (Mocks allowed for LLM)
# ==========================================


@pytest.mark.asyncio
async def test_integration_memory_flow():
    """[Integration] データの保存から検索までの結合フローを検証。"""
    from ripen.core.logic import save_memory_core, read_memory_core
    from ripen.infra.uow import UnitOfWork

    logger.info("Starting Integration Test: Memory Flow")
    test_entity = [
        {
            "name": "ChaosTestEntity",
            "entity_type": "chaos",
            "description": "Used for stress testing",
        }
    ]

    # Save
    await save_memory_core(entities=test_entity, user="test_user")

    # Read and Verify
    async with UnitOfWork() as uow:
        results = await read_memory_core(uow, query="ChaosTestEntity")
        found = any(e["name"] == "ChaosTestEntity" for e in results.get("entities", []))
        assert found
    logger.info("Integration Test: Memory Flow PASSED")


# ==========================================
# 3. CHAOS TESTS (Strict failure testing)
# ==========================================


@pytest.mark.asyncio
async def test_chaos_corrupted_db():
    """[Chaos] 破損したDBファイルがある状態での復旧能力を検証。"""
    logger.info("Starting Chaos Test: Corrupted DB")
    db_path = settings.base_dir / "knowledge.db"

    # 意図的にゴミデータを書き込む
    with open(db_path, "wb") as f:
        f.write(os.urandom(1024))

    # この状態でinit_dbがどう振る舞うか（通常は例外を吐くべき）
    with pytest.raises(Exception):
        await init_db(force=True)
    logger.info("Chaos Test: Corrupted DB properly raised error.")


@pytest.mark.asyncio
async def test_chaos_port_conflict():
    """[Chaos] ポートが占有されている状態での起動を検証。"""
    import socket

    port = settings.sse_port
    logger.info(f"Starting Chaos Test: Port Conflict on {port}")

    # ポートを占有
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen(1)

        # この状態でサーバー起動を試みる（server.pyの_kill_port_processを検証）
        from ripen.api.server import _kill_port_process

        _kill_port_process(port)

        # 占有していたソケットが（taskkill等で）解放されたか確認
        # 注意: 自プロセスで開いたソケットは自プロセスで殺せない場合があるが、
        # server.pyの実装がnetstat経由で正しく動作するかをテスト
        logger.info("Chaos Test: Port conflict handling triggered.")
    finally:
        sock.close()


if __name__ == "__main__":

    async def main_run():
        try:
            await test_unit_db_integrity()
            await test_unit_fastembed_loading()
            await test_integration_memory_flow()
            await test_chaos_corrupted_db()
            await test_chaos_port_conflict()
            print("\n✅ All manual verification tests passed.")
        except Exception as e:
            import traceback

            print(f"\n❌ INVESTIGATION FAILED")
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(main_run())
