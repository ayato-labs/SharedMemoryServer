import asyncio
import sys
import json
import subprocess

async def run_test():
    # Use the venv python to run the server as a subprocess
    # We want to emulate what the MCP client does: send JSON-RPC via stdin
    venv_python = r"c:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\.venv\Scripts\python.exe"
    
    process = subprocess.Popen(
        [venv_python, "-m", "shared_memory.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=0
    )

    def send_rpc(method, params):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        process.stdin.write(json.dumps(msg) + "\n")
        process.stdin.flush()

    # Wait for server to start? MCP servers are usually ready immediately but lifespan might take time.
    # FastMCP lifespan runs on startup.
    
    print("Sending initialize...")
    send_rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}})
    
    # Read response
    line = process.stdout.readline()
    print(f"Response: {line}")

    print("Sending tools/list...")
    send_rpc("tools/list", {})
    line = process.stdout.readline()
    print(f"Response: {line}")

    print("Sending tools/call for read_memory...")
    send_rpc("tools/call", {"name": "read_memory", "arguments": {"query": None}})
    
    # Read until we get a result or EOF
    while True:
        line = process.stdout.readline()
        if not line:
            print("EOF detected!")
            break
        print(f"Tool Result: {line}")
        if "result" in line:
            break

    # Check stderr for crashes
    stderr_out = process.stderr.read()
    if stderr_out:
        print(f"Stderr: {stderr_out}")

    process.terminate()

if __name__ == "__main__":
    asyncio.run(run_test())
