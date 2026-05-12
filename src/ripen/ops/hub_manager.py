import subprocess
import sys
import time
import socket
from pathlib import Path
from ripen.common.utils import get_logger

logger = get_logger("hub_manager")

def is_hub_running(port: int = 8377) -> bool:
    """Checks if the Ripen Hub is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def ensure_hub_running(port: int = 8377) -> bool:
    """
    Ensures the Ripen Hub is running. If not, starts it in the background.
    Returns True if Hub is confirmed running.
    """
    if is_hub_running(port):
        logger.info(f"Ripen Hub is already running on port {port}")
        return True

    logger.info(f"Ripen Hub not detected on port {port}. Attempting to start in background...")
    
    # On Windows, we use CREATE_NO_WINDOW and DETACHED_PROCESS to run in background
    # We use 'uv run ripen --sse' as the command
    try:
        # Determine the command to run. 
        # If we are running via uv, we should use 'uv run ripen --sse'
        # To be safe, we use 'sys.executable -m ripen.api.server --sse' 
        # but since 'ripen' is a registered script, 'ripen --sse' should work if in path.
        
        cmd = [sys.executable, "-m", "ripen.api.server", "--sse", "--port", str(port)]
        
        # Windows specific detached process flags
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True
        )
        
        # Wait for Hub to be ready
        retries = 0
        while retries < 10:
            time.sleep(1.0)
            if is_hub_running(port):
                logger.info("Ripen Hub successfully started in background.")
                return True
            retries += 1
            
        logger.error("Timed out waiting for Ripen Hub to start.")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start Ripen Hub in background: {e}")
        return False
