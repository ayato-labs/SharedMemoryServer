import subprocess
import sys
import os
import time

def test_extreme_guard():
    print("Testing Ripen Extreme Guard...")
    
    # We will run server.py with a fake argument to trigger an error
    # or just let it fail naturally if it can't find a dependency.
    # But a better way is to set an environment variable that server.py checks to crash.
    
    env = os.environ.copy()
    # We don't have a crash-on-purpose flag yet, but we can try to start it on a busy port
    # Or just use the fact that it might crash if we pass garbage.
    
    # Let's try running ripen with an invalid activation key which might fail
    # or just run the server script directly and hope for a crash.
    
    # Actually, let's create a temporary broken server.py to test the logic
    # NO, I should test the actual server.py.
    
    print("Running Ripen in SSE mode on an invalid port to trigger potential issues...")
    # This might not crash, it might just log a warning.
    
    # Best way: Use a python script that imports ripen.api.server and calls main()
    # but we wrap it in a way that we can see the output.
    
    cmd = [sys.executable, "-m", "ripen.api.server", "--sse", "--port", "99999"] # Invalid port
    
    try:
        # We use a short timeout because if it works, it hangs (it's a server).
        # If it crashes, it should print the guard message and wait.
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        
        print("Waiting for output...")
        time.sleep(3)
        
        # Check if process is still alive. If it's alive and waiting for input, it's working!
        if process.poll() is None:
            print("Process is still running (good, if it didn't crash).")
            process.terminate()
        else:
            out, err = process.communicate()
            print(f"Process exited with code: {process.returncode}")
            if "[CRITICAL FAILURE]" in out or "[CRITICAL FAILURE]" in err:
                print("SUCCESS: Extreme Guard detected!")
            else:
                print("FAILURE: Extreme Guard not detected in output.")
                print("STDOUT:", out)
                print("STDERR:", err)

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_extreme_guard()
