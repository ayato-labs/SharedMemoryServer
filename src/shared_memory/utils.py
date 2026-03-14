import os
import sys

def log_error(msg: str, e: Exception = None):
    error_msg = f"[SharedMemoryServer ERROR] {msg}"
    if e:
        error_msg += f": {e}"
    sys.stderr.write(error_msg + "\n")

def get_db_path():
    return os.environ.get("MEMORY_DB_PATH", "shared_memory.db")

def get_bank_dir():
    return os.environ.get("MEMORY_BANK_DIR", "memory-bank")
