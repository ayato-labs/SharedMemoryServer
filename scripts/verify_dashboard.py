import asyncio
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ripen.core.logic import save_memory_core
from ripen.infra.database import async_get_connection, init_db
from ripen.ops import management

async def verify():
    print("--- Dashboard & Conflict Resolution Verification ---")
    await init_db(force=True)
    
    # Clean wipe for testing
    async with await async_get_connection() as conn:
        print("Cleaning tables for fresh test...")
        await conn.execute("DELETE FROM observations")
        await conn.execute("DELETE FROM conflicts")
        await conn.execute("DELETE FROM entities")
        await conn.commit()
    
    # 1. Save initial knowledge
    print("\n1. Saving initial knowledge...")
    await save_memory_core(
        observations=[{"entity_name": "ProjectX", "content": "The deadline is June 1st."}]
    )
    
    # 2. Trigger a conflict
    print("\n2. Triggering a conflict (contradicting information)...")
    result = await save_memory_core(
        observations=[{"entity_name": "ProjectX", "content": "The deadline is actually July 15th."}]
    )
    print(f"Result: {result}")
    
    # 3. Check conflicts table
    print("\n3. Checking unresolved conflicts...")
    conflicts = await management.get_unresolved_conflicts_logic()
    for c in conflicts:
        print(f"ID: {c['id']}, Entity: {c['entity']}, Reason: {c['reason']}")
    
    if not conflicts:
        print("FAILED: No conflict detected.")
        return

    # 4. Resolve conflict (Approve)
    latest_conflict = conflicts[0] # The list is ordered by DESC detected_at
    print(
        f"\n4. Resolving conflict {latest_conflict['id']} "
        f"for {latest_conflict['entity']} (APPROVE)..."
    )
    res = await management.resolve_conflict_logic(latest_conflict['id'], "approve")
    print(f"Resolution result: {res}")
    
    # 5. Verify promotion
    print("\n5. Verifying promotion to observations...")
    async with await async_get_connection() as conn:
        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name = 'ProjectX'"
        )
        rows = await cursor.fetchall()
        print("Observations for ProjectX:")
        for r in rows:
            print(f"- {r[0]}")
    
    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify())
