import subprocess
import json
import time
import sys

def log_test(msg):
    with open("scratch/test_proxy.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} | {msg}\n")

def test_proxy():
    log_test("Starting Proxy test...")
    # Start proxy process using source code
    cmd = ["uv", "run", "python", "-m", "ripen.api.proxy"]
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1
    )
    
    def send(req):
        line = json.dumps(req)
        log_test(f"SEND: {req['method']} | {line}")
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
        
    def recv():
        log_test("Waiting for RECV...")
        line = proc.stdout.readline()
        if line:
            log_test(f"RECV RAW: {line}")
            data = json.loads(line)
            log_test(f"RECV PARSED: {data.get('id')} | {data.get('result') or data.get('error') or 'notification'}")
            return data
        log_test("RECV EMPTY (EOF)")
        return None

    try:
        # 1. Initialize
        send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        })
        
        # Wait for response
        for _ in range(5):
            res = recv()
            if res and res.get("id") == 1:
                break
            time.sleep(1)
        
        # 2. List Tools
        send({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        for _ in range(5):
            res = recv()
            if res and res.get("id") == 2:
                break
            time.sleep(1)

    finally:
        proc.terminate()
        print("Test finished.")

if __name__ == "__main__":
    test_proxy()
