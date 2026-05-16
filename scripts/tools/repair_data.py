import os
import sqlite3
import sys

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

from ripen.common.utils import get_db_path


def analyze_and_fix_orphans(db_path, dry_run=True):
    print(f"\n--- Analyzing Data Integrity for: {db_path} ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # 1. Orphaned Embeddings Analysis
        print("\n[1] Analyzing Orphaned Embeddings...")
        cursor = conn.execute("""
            SELECT content_id, COUNT(*) as count 
            FROM embeddings 
            WHERE content_id NOT IN (SELECT name FROM entities) 
            AND content_id NOT IN (SELECT filename FROM bank_files)
            GROUP BY content_id
        """)
        orphans = cursor.fetchall()
        print(f"Found {len(orphans)} unique content_ids with orphaned embeddings.")
        if orphans:
            print("Sample orphaned IDs:", [r["content_id"] for r in orphans[:5]])
            if not dry_run:
                print("Deleting orphaned embeddings...")
                conn.execute("""
                    DELETE FROM embeddings 
                    WHERE content_id NOT IN (SELECT name FROM entities) 
                    AND content_id NOT IN (SELECT filename FROM bank_files)
                """)
                print("Cleanup complete.")

        # 2. Broken Relations Analysis
        print("\n[2] Analyzing Broken Relations...")
        cursor = conn.execute("""
            SELECT subject, object 
            FROM relations 
            WHERE subject NOT IN (SELECT name FROM entities) 
            OR object NOT IN (SELECT name FROM entities)
        """)
        broken = cursor.fetchall()
        print(f"Found {len(broken)} relations pointing to missing entities.")
        if broken:
            # Analyze missing entities
            missing_entities = set()
            for r in broken:
                # Check which one is missing
                c = conn.execute("SELECT name FROM entities WHERE name = ?", (r["subject"],))
                if not c.fetchone():
                    missing_entities.add(r["subject"])
                c = conn.execute("SELECT name FROM entities WHERE name = ?", (r["object"],))
                if not c.fetchone():
                    missing_entities.add(r["object"])

            print(f"Missing entities causing broken relations: {list(missing_entities)[:10]}...")

            if not dry_run:
                print("Deleting broken relations...")
                conn.execute("""
                    DELETE FROM relations 
                    WHERE subject NOT IN (SELECT name FROM entities) 
                    OR object NOT IN (SELECT name FROM entities)
                """)
                print("Cleanup complete.")

        # 3. Orphaned Observations Analysis
        print("\n[3] Analyzing Orphaned Observations...")
        cursor = conn.execute("""
            SELECT entity_name, COUNT(*) as count 
            FROM observations 
            WHERE entity_name NOT IN (SELECT name FROM entities)
            AND entity_name != 'Global'
            GROUP BY entity_name
        """)
        obs_orphans = cursor.fetchall()
        print(f"Found {len(obs_orphans)} entities with orphaned observations.")
        if obs_orphans:
            print("Sample orphaned entity names:", [r["entity_name"] for r in obs_orphans[:5]])
            if not dry_run:
                print("Deleting orphaned observations...")
                conn.execute("""
                    DELETE FROM observations 
                    WHERE entity_name NOT IN (SELECT name FROM entities)
                    AND entity_name != 'Global'
                """)
                print("Cleanup complete.")

        if not dry_run:
            conn.commit()
            print("\nDatabase optimized and committed.")
            # Run VACUUM to reclaim space
            print("Running VACUUM...")
            conn.execute("VACUUM")
            print("Done.")
        else:
            print("\nDry run complete. No changes made.")

    except Exception as e:
        print(f"Error during analysis: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    path = get_db_path()
    dry_run = "--fix" not in sys.argv
    analyze_and_fix_orphans(path, dry_run=dry_run)

    if dry_run:
        print("\nTo apply fixes, run: .venv/Scripts/python.exe scripts/tools/repair_data.py --fix")
