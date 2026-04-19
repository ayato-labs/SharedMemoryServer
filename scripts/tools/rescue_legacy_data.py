import asyncio
import json
import os
import sqlite3

# To import SharedMemoryServer logic
import sys

project_root = os.getcwd()
sys.path.insert(0, os.path.join(project_root, "src"))

from shared_memory.database import async_get_connection, init_db  # noqa: E402


async def rescue_data():
    legacy_db = os.path.join(project_root, "archive", "legacy_db", "shared_memory.db")
    if not os.path.exists(legacy_db):
        print(f"Legacy DB not found at {legacy_db}")
        return

    print(f"Starting rescue from {legacy_db}...")
    await init_db()

    conn_legacy = sqlite3.connect(legacy_db)
    conn_legacy.row_factory = sqlite3.Row
    cursor_legacy = conn_legacy.cursor()

    # 1. Entities
    try:
        cursor_legacy.execute("SELECT * FROM entities")
        entities = cursor_legacy.fetchall()
        print(f"Found {len(entities)} entities in legacy DB.")

        async with await async_get_connection() as conn_new:
            for e in entities:
                e_dict = dict(e)
                # Audit log for the rescue action
                meta = json.dumps({"source": "legacy_rescue", "original_data": e_dict})

                await conn_new.execute(
                    "INSERT OR IGNORE INTO entities "
                    "(name, entity_type, description, importance, updated_by) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        e_dict["name"],
                        e_dict.get("entity_type"),
                        e_dict.get("description"),
                        e_dict.get("importance", 5),
                        "rescue_script",
                    ),
                )
                await conn_new.execute(
                    "INSERT INTO audit_logs "
                    "(table_name, content_id, action, new_data, agent_id, meta_data) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "entities",
                        e_dict["name"],
                        "RESCUE",
                        json.dumps(e_dict),
                        "rescue_script",
                        meta,
                    ),
                )
            await conn_new.commit()
            print("Entities merged into active DB.")

    except Exception as e:
        print(f"Entity rescue failed: {e}")

    # 2. Relations
    try:
        cursor_legacy.execute("SELECT * FROM relations")
        relations = cursor_legacy.fetchall()
        print(f"Found {len(relations)} relations in legacy DB.")

        async with await async_get_connection() as conn_new:
            for r in relations:
                r_dict = dict(r)
                # handle old vs new column names
                subj = r_dict.get("subject") or r_dict.get("source")
                obj = r_dict.get("object") or r_dict.get("target")
                pred = r_dict.get("predicate") or r_dict.get("relation_type")

                if subj and obj and pred:
                    await conn_new.execute(
                        "INSERT OR IGNORE INTO relations "
                        "(subject, object, predicate, created_by) "
                        "VALUES (?, ?, ?, ?)",
                        (subj, obj, pred, "rescue_script"),
                    )
            await conn_new.commit()
            print("Relations merged.")
    except Exception as e:
        print(f"Relation rescue skipped or failed: {e}")

    # 3. Observations
    try:
        cursor_legacy.execute("SELECT * FROM observations")
        obs = cursor_legacy.fetchall()
        print(f"Found {len(obs)} observations in legacy DB.")

        async with await async_get_connection() as conn_new:
            for o in obs:
                o_dict = dict(o)
                await conn_new.execute(
                    "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
                    (o_dict["entity_name"], o_dict["content"], "rescue_script"),
                )
            await conn_new.commit()
            print("Observations merged.")
    except Exception as e:
        print(f"Observation rescue skipped or failed: {e}")

    conn_legacy.close()
    print("Rescue complete.")


if __name__ == "__main__":
    asyncio.run(rescue_data())
