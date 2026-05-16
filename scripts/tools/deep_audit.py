import os
import sqlite3
import sys
from datetime import datetime

# Setup paths
project_root = os.getcwd()
sys.path.insert(0, os.path.join(project_root, "src"))

from ripen.common.utils import get_db_path, get_thoughts_db_path


def audit_db(name, path):
    print(f"\n--- Auditing {name} ---")
    print(f"Path: {path}")

    if not os.path.exists(path):
        print("Status: MISSING")
        return

    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # 1. Table Overview
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"Tables: {', '.join(tables)}")

        # 2. Detailed Stats
        for table in tables:
            if (
                table.endswith("_fts")
                or table.endswith("_data")
                or table.endswith("_idx")
                or table.endswith("_docsize")
                or table.endswith("_config")
            ):
                continue  # Skip FTS internal tables

            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  [{table:15}] {count:6} rows")

            # Check for recent activity
            try:
                # Some tables might not have timestamp
                cursor = conn.execute(f"SELECT MAX(timestamp) FROM {table}")
                last_act = cursor.fetchone()[0]
                if last_act:
                    print(f"    Last activity: {last_act}")
            except Exception:
                pass

        # 3. Data Quality Checks (Deep Analysis)
        if name == "Knowledge DB":
            # Orphaned Embeddings check
            cursor = conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE content_id NOT IN (SELECT name FROM entities) AND content_id NOT IN (SELECT filename FROM bank_files)"
            )
            orphans = cursor.fetchone()[0]
            if orphans > 0:
                print(f"  [QUALITY WARNING] {orphans} orphaned embeddings detected!")
            else:
                print("  [QUALITY OK] No orphaned embeddings.")

            # Broken Relations check
            cursor = conn.execute(
                "SELECT COUNT(*) FROM relations WHERE subject NOT IN (SELECT name FROM entities) OR object NOT IN (SELECT name FROM entities)"
            )
            broken_rel = cursor.fetchone()[0]
            if broken_rel > 0:
                print(
                    f"  [QUALITY WARNING] {broken_rel} relations pointing to non-existent entities!"
                )
            else:
                print("  [QUALITY OK] All relations link to valid entities.")

        if name == "Thoughts DB":
            # FTS5 Sync check
            cursor = conn.execute("SELECT COUNT(*) FROM thought_history")
            real_count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM thought_history_fts")
            fts_count = cursor.fetchone()[0]
            if real_count != fts_count:
                print(
                    f"  [QUALITY WARNING] FTS5 index desync! History: {real_count}, FTS: {fts_count}"
                )
            else:
                print("  [QUALITY OK] FTS5 index is in sync.")

        conn.close()
    except Exception as e:
        print(f"Error during audit: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print(" SHARED MEMORY SERVER - DEEP AUDIT REPORT")
    print(f" Generated at: {datetime.now().isoformat()}")
    print("=" * 60)

    audit_db("Knowledge DB", get_db_path())
    audit_db("Thoughts DB", get_thoughts_db_path())

    print("\n" + "=" * 60)
    print(" Audit Complete.")
    print("=" * 60)
