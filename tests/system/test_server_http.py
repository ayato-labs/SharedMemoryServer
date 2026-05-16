import os
import signal
import subprocess
import sys
import time

import httpx
import pytest


@pytest.fixture(scope="module")
def server_process():
    """Starts the Ripen Hub server in a background process."""
    env = os.environ.copy()
    
    # Ensure we use the correct path to src
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = src_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = src_path

    # Use a specific directory in the project
    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db"))
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(os.path.join(test_dir, "bank"), exist_ok=True)
    
    env["MEMORY_DB_PATH"] = os.path.join(test_dir, "knowledge.db")
    env["THOUGHTS_DB_PATH"] = os.path.join(test_dir, "thoughts.db")
    env["MEMORY_BANK_DIR"] = os.path.join(test_dir, "bank")

    # Use a file for logs to avoid blocking on pipe buffer
    log_file_path = os.path.join(test_dir, "server.log")
    log_file = open(log_file_path, "w", encoding="utf-8")

    # Start the server
    process = subprocess.Popen(
        [sys.executable, "-m", "ripen.api.server", "--port", "8377"],
        stdout=log_file,
        stderr=log_file,
        text=True,
        env=env
    )
    
    # Wait for the server to start and listen on port
    time.sleep(10)
    
    yield process
    
    # Teardown: Stop the server
    if process.poll() is None:
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
        
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Server did not terminate gracefully, killing it...")
            process.kill()
            process.wait()
            
    log_file.close()
    
    # Read logs for debugging output in test
    print("\n--- Server Logs ---")
    if os.path.exists(log_file_path):
        with open(log_file_path, encoding="utf-8") as f:
            print(f.read())
    print("-------------------")
    
    # Clean up test database
    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception as e:
        print(f"DEBUG: Failed to clean up test_dir: {e}")


@pytest.mark.asyncio
@pytest.mark.system
async def test_server_http_connectivity(server_process):
    """
    System Test: サーバーが起動し、HTTPリクエストを受け付けることを検証。
    """
    # サーバーが生きていることを確認
    assert server_process.poll() is None, "Server process died before test started"

    # HTTPリクエストの送信
    async with httpx.AsyncClient() as client:
        # 1. /dashboard にリクエスト
        try:
            response = await client.get("http://localhost:8377/dashboard/", timeout=5.0)
            assert response.status_code in [200, 307, 401, 404]
            print(f"DEBUG: Dashboard response status: {response.status_code}")
        except httpx.ConnectError:
            pytest.fail("Failed to connect to the server on port 8377 for dashboard")

        # 2. MCP プロトコル（JSON-RPC）のエンドポイントを叩く
        try:
            response = await client.post(
                "http://localhost:8377/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"}
                    }
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"
                },
                timeout=5.0
            )
            assert response.status_code in [200, 406]
        except httpx.ConnectError:
            pytest.fail("Failed to connect to the server on port 8377 for MCP request")
        except Exception as e:
            pytest.fail(f"MCP Request failed with unexpected error: {e}")
