import subprocess
import time
import httpx
import sys
import os

def verify_server():
    print("Starting Ripen server for verification...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    
    process = subprocess.Popen(
        ["uv", "run", "python", "-m", "ripen.api.server", "--sse", "--port", "8377"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        encoding='utf-8',
        errors='replace'
    )

    print("Waiting for server to initialize (lifespan)...")
    success = False
    
    for i in range(30):
        time.sleep(1)
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get("http://localhost:8377/dashboard")
                if resp.status_code == 200:
                    print(f"Server is UP and responding at http://localhost:8377/dashboard (after {i+1}s)")
                    success = True
                    break
        except Exception:
            pass
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print("Server process died prematurely!")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            break
            
    print("Cleaning up server process...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        
    if not success:
        print("Server failed to respond within 30 seconds.")
        sys.exit(1)
    else:
        print("Verification SUCCESSFUL!")

if __name__ == "__main__":
    verify_server()
