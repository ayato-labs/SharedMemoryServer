import socket
import subprocess
import sys
import time
from pathlib import Path

from ripen.common.utils import get_logger

logger = get_logger("hub_manager")

def is_hub_running(port: int = 8377) -> bool:
    """Checks if the Ripen Hub is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def is_hub_reachable(url: str, timeout: float = 2.0) -> bool:
    """
    Checks if a remote Ripen Hub is reachable via HTTP.
    url should be like 'http://1.2.3.4:8377'
    """
    import urllib.request
    try:
        # We append /dashboard/ to check if the app is actually there
        test_url = f"{url.rstrip('/')}/dashboard/"
        with urllib.request.urlopen(test_url, timeout=timeout) as response:
            return response.getcode() == 200
    except Exception as e:
        logger.debug(f"Hub reachability check failed for {url}: {e}")
        return False

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
        
        # Set up diagnostic logging for startup
        from ripen.common.config import settings
        log_dir = Path(settings.base_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        startup_log_path = log_dir / "hub_startup.log"
        
        # Clear previous startup log
        if startup_log_path.exists():
            try:
                startup_log_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Could not clear previous startup log: {e}")
                
        logger.info(f"Background Hub logs will be written to: {startup_log_path}")
        
        # Open the log file for both stdout and stderr
        startup_log = open(startup_log_path, "a", encoding="utf-8")
        
        # Multi-platform background process configuration
        popen_kwargs = {
            "stdout": startup_log,
            "stderr": startup_log,
            "stdin": subprocess.DEVNULL,
            "close_fds": True
        }
        
        if sys.platform == "win32":
            # Windows specific detached process flags
            # Note: On Windows, DETACHED_PROCESS and handles redirection can be tricky.
            # But CREATE_NO_WINDOW should be enough for "silent" startup.
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            # POSIX (Linux/Mac) backgrounding
            popen_kwargs["start_new_session"] = True
            
        logger.debug(f"Running background command: {' '.join(cmd)}")
        subprocess.Popen(cmd, **popen_kwargs)
        
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
        logger.error(f"Failed to start Ripen Hub in background: {e}", exc_info=True)
        return False
