import argparse
import asyncio

from shared_memory import logic, thought_logic


async def run_history(args):
    history = await logic.get_audit_history_core(limit=args.limit)
    if not history:
        print("No audit history found.")
        return
    print(
        f"{'ID':<5} | {'Timestamp':<20} | {'Action':<10} | {'Table':<15} | {'Agent':<15}"
    )
    print("-" * 75)
    for entry in history:
        print(
            f"{entry['id']:<5} | {entry['timestamp']:<20} | {entry['action']:<10} | {entry['table']:<15} | {entry['agent']:<15}"
        )


async def run_repair(args):
    print("Repairing memory bank files from database...")
    result = await logic.repair_memory_core()
    print(result)


async def run_rollback(args):
    print(f"Rolling back to audit ID {args.id}...")
    result = await logic.rollback_memory_core(args.id)
    print(result)


async def run_snapshot(args):
    if args.subcommand == "create":
        res = await logic.create_snapshot_core(args.name, args.description or "")
        print(res)
    elif args.subcommand == "restore":
        res = await logic.restore_snapshot_core(args.id)
        print(res)
    elif args.subcommand == "list":
        # We need a list_snapshots function in management or logic
        from shared_memory import management

        snapshots = await management.list_snapshots_logic()
        if not snapshots:
            print("No snapshots found.")
            return
        print(f"{'ID':<5} | {'Timestamp':<20} | {'Name':<20}")
        print("-" * 50)
        for s in snapshots:
            print(f"{s['id']:<5} | {s['timestamp']:<20} | {s['name']:<20}")


async def run_health(args):
    print("Running system diagnostics...")
    health = await logic.get_memory_health_core()
    import json

    print(json.dumps(health, indent=2, ensure_ascii=False))


async def run_recover_thoughts(args):
    print("Recovering undistilled thoughts...")
    await thought_logic.recover_undistilled_sessions()
    print("Recovery scan complete.")


def main():
    parser = argparse.ArgumentParser(description="SharedMemoryServer Admin CLI")
    subparsers = parser.add_subparsers(dest="command", help="Admin commands")

    # History
    hist_parser = subparsers.add_parser("history", help="View audit history")
    hist_parser.add_argument(
        "--limit", type=int, default=20, help="Number of entries to show"
    )

    # Repair
    subparsers.add_parser("repair", help="Repair memory bank files from DB")

    # Rollback
    rb_parser = subparsers.add_parser(
        "rollback", help="Rollback to a specific audit ID"
    )
    rb_parser.add_argument("id", type=int, help="Audit ID to rollback to")

    # Snapshot
    snap_parser = subparsers.add_parser("snapshot", help="Manage snapshots")
    snap_sub = snap_parser.add_subparsers(dest="subcommand")

    create_snap = snap_sub.add_parser("create", help="Create a snapshot")
    create_snap.add_argument("name", help="Snapshot name")
    create_snap.add_argument("--description", help="Optional description")

    restore_snap = snap_sub.add_parser("restore", help="Restore a snapshot")
    restore_snap.add_argument("id", type=int, help="Snapshot ID")

    snap_sub.add_parser("list", help="List snapshots")

    # Health
    subparsers.add_parser("health", help="Run system diagnostics")

    # Recover Thoughts
    subparsers.add_parser("recover-thoughts", help="Manually trigger thought recovery")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Map commands to functions
    cmd_map = {
        "history": run_history,
        "repair": run_repair,
        "rollback": run_rollback,
        "snapshot": run_snapshot,
        "health": run_health,
        "recover-thoughts": run_recover_thoughts,
    }

    asyncio.run(cmd_map[args.command](args))


if __name__ == "__main__":
    main()
