import asyncio
import json
import os
from datetime import datetime

import sys
project_root = os.getcwd()
sys.path.insert(0, os.path.join(project_root, "src"))

import aiosqlite
from shared_memory.utils import get_db_path, get_thoughts_db_path

async def view_trace():
    db_knowledge = get_db_path()
    db_thoughts = get_thoughts_db_path()

    print("=" * 60)
    print(" SHARED MEMORY SERVER - UNIFIED TRACE VIEWER")
    print("=" * 60)

    # Fetch Audit Logs
    audit_data = []
    if os.path.exists(db_knowledge):
        async with aiosqlite.connect(db_knowledge) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20")
            rows = await cursor.fetchall()
            for r in rows:
                d = dict(r)
                d["source"] = "AUDIT"
                audit_data.append(d)

    # Fetch Thoughts
    thought_data = []
    if os.path.exists(db_thoughts):
        async with aiosqlite.connect(db_thoughts) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM thought_history ORDER BY timestamp DESC LIMIT 20")
            rows = await cursor.fetchall()
            for r in rows:
                d = dict(r)
                d["source"] = "THOUGHT"
                thought_data.append(d)

    # Merge and sort
    all_trace = audit_data + thought_data
    all_trace.sort(key=lambda x: x["timestamp"], reverse=True)

    for item in all_trace[:30]:
        ts = item["timestamp"]
        source = item["source"]
        
        if source == "THOUGHT":
            sid = item["session_id"]
            num = item["thought_number"]
            txt = item["thought"][:50] + "..." if len(item["thought"]) > 50 else item["thought"]
            meta = item.get("meta_data")
            print(f"[{ts}] [THOUGHT] Session:{sid} #{num} | {txt}")
            if meta:
                print(f"    -> Meta: {meta}")
        else:
            tbl = item["table_name"]
            action = item["action"]
            cid = item["content_id"]
            meta = item.get("meta_data")
            print(f"[{ts}] [AUDIT  ] {action} on {tbl}:{cid}")
            if meta:
                print(f"    -> Meta: {meta}")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(view_trace())
