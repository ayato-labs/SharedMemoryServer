import os
import sqlite3
import sys

# Setup relative paths for the utility
project_root = os.getcwd()
sys.path.insert(0, os.path.join(project_root, "src"))

from shared_memory.database import get_db_path  # noqa: E402
from shared_memory.utils import get_thoughts_db_path  # noqa: E402


def run_diagnostics():
    """CLI utility to inspect SharedMemoryServer database health and schema."""
    print("=" * 60)
    print(" SHARED MEMORY SERVER - DATABASE DIAGNOSTICS")
    print("=" * 60)

    kb_path = get_db_path()
    th_path = get_thoughts_db_path()

    diagnostics = [
        ("Knowledge DB", kb_path),
        ("Thoughts DB", th_path),
    ]

    for name, path in diagnostics:
        exists = os.path.exists(path)
        status = "OK" if exists else "MISSING"
        print(f"\n[{name}]")
        print(f"  Path:   {path}")
        print(f"  Status: {status}")

        if exists:
            try:
                # Use a standard relative connection
                conn = sqlite3.connect(path)
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                print(f"  Tables: {', '.join(tables) if tables else 'NONE'}")

                # Check for critical table existence
                if name == "Knowledge DB":
                    critical = ["entities", "audit_logs", "embedding_cache"]
                    missing = [t for t in critical if t not in tables]
                    if missing:
                        print(f"  WARNING: Missing tables: {', '.join(missing)}")
                    else:
                        print("  Schema:  VERIFIED")

                conn.close()
            except Exception as e:
                print(f"  ERROR:  Could not read database: {e}")

    print("\n" + "=" * 60)
    print(" CWD: " + os.getcwd())
    print("=" * 60)


if __name__ == "__main__":
    run_diagnostics()
