import asyncio
import os
import signal
import subprocess
import sys
import time
from unittest.mock import patch

import httpx
import pytest
from tests.unit.fake_client import FakeGeminiClient

from ripen.core import logic


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_invalid_inputs():
    """
    異常系テスト: 不正な入力（None、空文字、壊れた辞書）を渡した場合。
    """
    # 1. None を渡した場合
    res = await logic.save_memory_core(entities=None, observations=None)
    assert res == ""

    # 2. 空文字を含むリストを渡した場合
    res = await logic.save_memory_core(
        entities=["", "  "],
        observations=[{"content": "", "entity_name": ""}]
    )
    # 正常に処理され、0件保存などの結果が返ることを確認
    assert "Saved 0" in res or res == ""

    # 3. 壊れた辞書を渡した場合
    malformed_obs = [{"wrong_key": "data"}, ["not", "a", "dict"], "just a string"]
    try:
        res = await logic.save_memory_core(observations=malformed_obs)
        assert isinstance(res, str)
    except Exception as e:
        pytest.fail(f"save_memory_core crashed with malformed data: {e}")


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_ai_error_resilience():
    """
    異常系テスト: AI APIがエラーを返した場合の挙動。
    Expectation: APIエラーが発生しても、システムはクラッシュせず、
    適切に例外をスローするか、あるいはフォールバックする。
    """
    with patch(
        "ripen.infra.embeddings._run_engine_computation",
        side_effect=Exception("Rate Limit Exceeded")
    ):
        import uuid
        res = await logic.save_memory_core(
            entities=[{"name": "FailNode", "description": f"Unique fail {uuid.uuid4()}"}]
        )
        # save_memory_core は例外をキャッチして文字列を返す
        assert "AI Error" in res or "Rate Limit" in res or "Unexpected Error" in res


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_concurrent_saves():
    """
    負荷テスト: 多数の同時並行保存リクエストによるDBロックの検証。
    """
    tasks = []
    for i in range(10):
        tasks.append(
            logic.save_memory_core(
                entities=[f"ConcurrentEntity{i}"],
                observations=[{"content": f"Data {i}", "entity_name": f"ConcurrentEntity{i}"}],
                agent_id=f"agent_{i}"
            )
        )

    # FakeGeminiClient を使用して並行実行
    fake_client = FakeGeminiClient()
    with patch("ripen.infra.embeddings.get_gemini_client", return_value=fake_client):
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    for res in results:
        if isinstance(res, Exception):
            pytest.fail(f"Concurrent save failed: {res}")
        assert "Saved" in res or "success" in res.lower()


@pytest.fixture(scope="module")
def server_process():
    """Starts the Ripen Hub server in a background process for load testing."""
    env = os.environ.copy()
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = src_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = src_path

    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db_chaos"))
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(os.path.join(test_dir, "bank"), exist_ok=True)
    
    env["MEMORY_DB_PATH"] = os.path.join(test_dir, "knowledge.db")
    env["THOUGHTS_DB_PATH"] = os.path.join(test_dir, "thoughts.db")
    env["MEMORY_BANK_DIR"] = os.path.join(test_dir, "bank")

    log_file_path = os.path.join(test_dir, "server.log")
    log_file = open(log_file_path, "w", encoding="utf-8")

    # Start the server on a different port to avoid conflict
    process = subprocess.Popen(
        [sys.executable, "-m", "ripen.api.server", "--port", "8378"],
        stdout=log_file,
        stderr=log_file,
        text=True,
        env=env
    )
    
    time.sleep(10)
    yield process
    
    if process.poll() is None:
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            
    log_file.close()
    
    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_server_load(server_process):
    """
    負荷テスト: サーバーに対する並行リクエスト。
    """
    assert server_process.poll() is None, "Server process died before test started"

    async def send_request(i):
        async with httpx.AsyncClient() as client:
            # ダッシュボードへのリクエスト
            response = await client.get("http://localhost:8378/dashboard/", timeout=5.0)
            return response.status_code

    # 10個のリクエストを並行して送信
    tasks = [send_request(i) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, Exception):
            pytest.fail(f"Load request failed: {res}")
        assert res in [200, 307, 401, 404]
