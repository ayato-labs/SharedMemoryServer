import sqlite3
import json
import os
import sys

# Robust path addition
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

from ripen.common.utils import get_db_path

def deep_data_analysis():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("="*60)
    print(" RIPEN (ex SharedMemory) - PRODUCTION DATA ANALYSIS REPORT")
    print("="*60)

    # 1. Entity Statistics
    print("\n[1] Entity Composition")
    cursor = conn.execute("SELECT entity_type, COUNT(*) as count FROM entities GROUP BY entity_type ORDER BY count DESC")
    for row in cursor.fetchall():
        print(f"  - {row['entity_type']:15}: {row['count']} items")

    # 2. Top Knowledge Assets (by Importance)
    print("\n[2] High-Value Knowledge (Top 10 by Importance)")
    cursor = conn.execute("SELECT name, importance, entity_type FROM entities ORDER BY importance DESC, updated_at DESC LIMIT 10")
    for row in cursor.fetchall():
        print(f"  - [{row['importance']:2}/10] {row['name']} ({row['entity_type']})")

    # 3. Connection Density
    print("\n[3] Graph Connectivity")
    cursor = conn.execute("SELECT COUNT(*) FROM relations")
    rel_count = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM entities")
    ent_count = cursor.fetchone()[0]
    density = rel_count / (ent_count * (ent_count - 1)) if ent_count > 1 else 0
    print(f"  - Total Entities : {ent_count}")
    print(f"  - Total Relations: {rel_count}")
    print(f"  - Graph Density  : {density:.4f}")

    # 4. Orphan Analysis (Deep Dive)
    print("\n[4] Orphaned Data Origins (Top 10)")
    cursor = conn.execute("""
        SELECT content_id, COUNT(*) as count 
        FROM embeddings 
        WHERE content_id NOT IN (SELECT name FROM entities) 
        AND content_id NOT IN (SELECT filename FROM bank_files)
        GROUP BY content_id ORDER BY count DESC LIMIT 10
    """)
    print("  Orphaned embeddings often come from deleted files or legacy indexing:")
    for row in cursor.fetchall():
        print(f"  - {row['content_id']} ({row['count']} vectors)")

    # 5. Recent Activity
    print("\n[5] Recent System Activity (Audit Logs)")
    cursor = conn.execute("SELECT action, table_name, count(*) as c FROM audit_logs GROUP BY action, table_name ORDER BY c DESC")
    for row in cursor.fetchall():
        print(f"  - {row['action']:8} on {row['table_name']:12}: {row['c']} times")

    print("\n" + "="*60)
    conn.close()

if __name__ == "__main__":
    deep_data_analysis()
