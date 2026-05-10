import os
import shutil
import sys
from pathlib import Path


def ask_confirmation(prompt: str) -> bool:
    """Helper to ask for Y/N confirmation."""
    while True:
        choice = input(f"{prompt} (y/n): ").lower().strip()
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


def perform_uninstall():
    """
    Performs a clean uninstall of Ripen data and shortcuts.
    """
    print("\n" + "!" * 60)
    print("  RIPEN UNINSTALLER - COMPLETE DATA ERASURE")
    print("!" * 60 + "\n")

    # 1. Warning
    print("\033[1;31mWARNING: This action will permanently delete all your knowledge data,\033[0m")
    print("\033[1;31mconfig files, logs, and desktop shortcuts.\033[0m")
    print("This cannot be undone.\n")

    if not ask_confirmation("Are you absolutely sure you want to proceed?"):
        print("\nUninstall cancelled.")
        return

    # 2. Identify data directory
    from ripen.common.config import settings

    base_dir = Path(settings.base_dir).resolve()

    print(f"\nTarget Data Directory: {base_dir}")
    if not ask_confirmation(f"Delete ALL data in '{base_dir}'?"):
        print("\nUninstall cancelled.")
        return

    # 3. Perform Cleanup
    print("\nStarting cleanup...")

    # A. Delete Shortcuts (Windows)
    if sys.platform == "win32":
        try:
            desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
            shortcut = desktop / "Ripen Hub.lnk"
            if shortcut.exists():
                shortcut.unlink()
                print("  [OK] Removed Desktop shortcut.")
        except Exception as e:
            print(f"  [ERROR] Failed to remove shortcut: {e}")

    # B. Delete Data Directory
    try:
        if base_dir.exists():
            shutil.rmtree(base_dir)
            print(f"  [OK] Removed data directory: {base_dir}")
    except Exception as e:
        print(f"  [ERROR] Failed to remove data directory: {e}")
        print("  Please ensure no other processes are using the database.")

    print("\n" + "=" * 60)
    print("\033[1;32mSUCCESS: Ripen data has been completely erased.\033[0m")
    print("=" * 60)

    # C. Instructions for Environment removal
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        print(f"\nFinal Step: Please manually delete the executable file:")
        print(f"  \033[1;36m{exe_path}\033[0m")
    else:
        print("\n\033[1;33m[NOTE for Python Users]\033[0m")
        print("To completely remove the Python environment:")
        print("  1. If installed as a tool: \033[1;36muv tool uninstall ripen\033[0m")
        print("  2. If using a local venv:  \033[1;36mrm -rf .venv\033[0m (in the project root)")
        print("  3. Finally, uninstall the package: \033[1;36mpip uninstall ripen\033[0m")

    print("\nGoodbye!\n")
    sys.exit(0)
