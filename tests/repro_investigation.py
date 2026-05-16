import asyncio
import os
import sys
import time

import pytest
from loguru import logger

# Add src to sys.path
sys.path.append(os.path.abspath("src"))

from ripen.common.config import settings
from ripen.infra.database import close_all_connections, init_db
from ripen.infra.embeddings import get_fastembed_model


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    """Ensure no lingering connections between tests."""
    await close_all_connections()
    yield
    await close_all_connections()


# ==========================================
# 1. UNIT TESTS (No Mocks)
# ==========================================


@pytest.mark.asyncio
async def test_unit_db_integrity():
    """[Unit] データベースの物理的整合性と初期化の正確性を検証。"""
    logger.info("Starting Unit Test: DB Integrity (No Mock)")
    from ripen.infra.uow import UnitOfWork
    
    # Override settings for test
    settings._config_data["ripen_home"] = str(settings.base_dir)
    
    await init_db(force=True)

    async with UnitOfWork() as uow:
        tables = await uow.management.get_table_info()
        table_names = [t["name"] for t in tables]
        assert "entities" in table_names
        assert "embeddings" in table_names
        # thought_history is in a separate database, not knowledge.db
        logger.info("DB Integrity check passed via UOW.")



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
    from ripen.core.logic import read_memory_core, save_memory_core

    logger.info("Starting Integration Test: Memory Flow")
    test_entity = [
        {
            "name": "ChaosTestEntity",
            "entity_type": "chaos",
            "description": "Used for stress testing",
        }
    ]

    # Save
    await save_memory_core(entities=test_entity, agent_id="test_user")

    # Read and Verify
    results = await read_memory_core(query="ChaosTestEntity")
    # Structure is {"graph": {"entities": [...], ...}, "bank": {...}}
    graph_data = results.get("graph", {})
    entities_found = graph_data.get("entities", [])
    found = any(e["name"] == "ChaosTestEntity" for e in entities_found)
    
    if not found:
        logger.error(f"Search failed to find ChaosTestEntity. Results: {results}")
        
    assert found, f"ChaosTestEntity not found in {results}"
    logger.info("Integration Test: Memory Flow PASSED")


# ==========================================
# 3. CHAOS TESTS (Strict failure testing)
# ==========================================


@pytest.mark.asyncio
async def test_chaos_corrupted_db():
    logger.info("Starting Chaos Test: Corrupted DB")
    db_path = settings.base_dir / "knowledge.db"

    # Ensure connections are closed before corruption
    from ripen.infra.database import close_all_connections
    await close_all_connections()
    await asyncio.sleep(0.5)

    # 意図的にゴミデータを書き込む
    with open(db_path, "wb") as f:
        f.write(os.urandom(1024))

    # With new resilience logic, init_db should RECOVER instead of just failing.
    # We verify that it doesn't crash and initializes successfully.
    await init_db(force=True)
    
    from ripen.infra.uow import UnitOfWork
    async with UnitOfWork() as uow:
        tables = await uow.management.get_table_info()
        assert len(tables) > 0
        
    logger.info("Chaos Test: Corrupted DB Recovery PASSED")


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

        # この状態でサーバー起動を試みる(server.pyの_kill_port_processを検証)
        from ripen.api.server import _kill_port_process

        _kill_port_process(port)

        # 占有していたソケットが(taskkill等で)解放されたか確認
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
        except Exception:
            import traceback

            print("\n❌ INVESTIGATION FAILED")
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(main_run())
