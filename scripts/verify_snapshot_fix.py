import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

try:
    from shared_memory.server import create_snapshot
    from shared_memory.database import init_db

    # Initialize DB first
    init_db()

    print("Attempting to create snapshot...")
    snapshot_id = create_snapshot()
    print(f"Success! Snapshot ID: {snapshot_id}")

except Exception as e:
    print(f"Failed with error: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
