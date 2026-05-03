import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from shared_memory.api import server


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_initialized_waits(fake_llm):
    """ensure_initialized が初期化完了まで待機することを検証"""
    # 初期状態を未初期化に設定
    if server._INITIALIZED_EVENT:
        server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    # 200ms後に初期化を完了させるタスク
    async def finish_init_delayed():
        await asyncio.sleep(0.2)
        if server._INITIALIZED_EVENT is None:
            server._INITIALIZED_EVENT = asyncio.Event()
        server._INITIALIZED_EVENT.set()

    asyncio.create_task(finish_init_delayed())

    # ensure_initialized を呼び出し(待機が発生するはず)
    # タイムアウトを設定して無限ループを防ぐ
    await asyncio.wait_for(server.ensure_initialized(), timeout=1.0)

    assert server._INITIALIZED_EVENT.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_background_init_success(fake_llm):
    """_background_init が正常に完了し、フラグを立てることを検証"""
    if server._INITIALIZED_EVENT:
        server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    with (
        patch("shared_memory.api.server.init_db", new_callable=AsyncMock) as mock_db,
        patch(
            "shared_memory.api.server.thought_logic.init_thoughts_db", new_callable=AsyncMock
        ) as mock_thought,
    ):
        await server._background_init()

        assert server._INITIALIZED_EVENT.is_set()
        assert server._INIT_ERROR is None
        assert mock_db.called
        assert mock_thought.called


@pytest.mark.asyncio
@pytest.mark.unit
async def test_background_init_failure(fake_llm):
    if server._INITIALIZED_EVENT:
        server._INITIALIZED_EVENT.clear()
    server._INIT_ERROR = None

    with (
        patch("shared_memory.api.server.init_db", side_effect=Exception("DB Crash")),
        patch("shared_memory.api.server.logger.error") as mock_log_error,
    ):
        await server._background_init()

        assert server._INITIALIZED_EVENT.is_set()
        assert server._INIT_ERROR is not None
        assert mock_log_error.called
        assert any(
            "[FATAL ERROR] Initialization failed" in call.args[0]
            for call in mock_log_error.call_args_list
        )
