import json
import subprocess


def test_mcp_server():
    # Start the server in stdio mode
    process = subprocess.Popen(
        ["uv", "run", "python", "src/shared_memory/server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    # Helper to send a request
    def send_request(method, params=None, req_id=1):
        request = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params:
            request["params"] = params

        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()

    # 1. Initialize
    send_request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
        req_id=1,
    )

    # Read response
    line = process.stdout.readline()

    # 2. List Tools
    send_request("tools/list", req_id=2)
    line = process.stdout.readline()
    with open("scratch/tools_list_raw.json", "w", encoding="utf-8") as f:
        f.write(line)

    process.terminate()


if __name__ == "__main__":
    test_mcp_server()
