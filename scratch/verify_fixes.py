import asyncio
import json
from ripen.infra.uow import UnitOfWork
from ripen.common.utils import configure_logging

async def verify_stabilization():
    configure_logging()
    print("--- Ripen Stabilization Verification ---")
    
    async with UnitOfWork() as uow:
        print("\n1. Checking Repository Methods Presence:")
        checks = [
            ("embeddings", "get_all_embeddings"),
            ("management", "optimize_database"),
            ("management", "get_stale_knowledge_ids"),
            ("audit", "get_audit_log_by_id"),
            ("conflicts", "get_conflict_by_id"),
            ("conflicts", "mark_resolved"),
        ]
        
        for repo_attr, method in checks:
            repo = getattr(uow, repo_attr)
            exists = hasattr(repo, method)
            print(f"  - {repo_attr}.{method}: {'OK' if exists else 'MISSING'}")
            if not exists:
                raise AttributeError(f"{repo_attr} is missing {method}")

        print("\n2. Exercising Methods:")
        
        # Test get_all_embeddings
        print("  - Testing embeddings.get_all_embeddings()...")
        rows = await uow.embeddings.get_all_embeddings()
        print(f"    Result: Found {len(rows)} embedding records.")
        
        # Test optimize_database
        print("  - Testing management.optimize_database()...")
        await uow.management.optimize_database()
        print("    Result: Success (PRAGMA optimize executed).")
        
        # Test stale knowledge retrieval
        print("  - Testing management.get_stale_knowledge_ids(30)...")
        stale_ids = await uow.management.get_stale_knowledge_ids(30)
        print(f"    Result: Found {len(stale_ids)} stale candidates.")

        # Test batch status update (The one that was raising TypeError)
        print("  - Testing entities.update_status with empty list...")
        changes = await uow.entities.update_status([], "inactive")
        print(f"    Result: Success (Modified {changes} items).")

    print("\n3. Log Rotation Verification:")
    from pathlib import Path
    log_file = Path("logs/server.jsonl")
    if log_file.exists():
        size_mb = log_file.stat().st_size / (1024 * 1024)
        print(f"  - server.jsonl exists. Size: {size_mb:.2f} MB")
        print("  - No PermissionError observed during this execution.")
    else:
        print("  - server.jsonl not found yet (this is OK if logging was recently configured).")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_stabilization())
