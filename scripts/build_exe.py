import os
import sys
import shutil
import subprocess
from pathlib import Path


def kill_existing_process():
    """Kills any running ripen.exe to release file locks."""
    if sys.platform == "win32":
        print("Checking for running ripen.exe processes...")
        try:
            # Use taskkill to silently close any existing ripen.exe
            subprocess.run(
                ["taskkill", "/F", "/IM", "ripen.exe", "/T"], capture_output=True, check=False
            )
        except Exception:
            pass


def build():
    base_dir = Path(__file__).parent.parent.absolute()
    dist_dir = base_dir / "dist"
    build_dir = base_dir / "build"

    # Ensure no existing process is locking the dist file
    kill_existing_process()

    print(f"Building Ripen EXE in {base_dir}...")

    # 1. Create a clean entry point
    entry_point = base_dir / "ripen_launcher.py"
    entry_content = """
import sys
import multiprocessing
import traceback
from ripen.api.server import main as server_main
from ripen.cli.init import main as init_main
from ripen.cli.admin_cli import main as admin_main

def run():
    multiprocessing.freeze_support()
    try:
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == "init":
                sys.argv.pop(1)
                init_main()
                return
            elif cmd == "admin":
                sys.argv.pop(1)
                admin_main()
                return
                
        server_main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\\n\033[1;31m[FATAL ERROR]\033[0m {e}")
        traceback.print_exc()
    finally:
        # Final safety net for frozen EXE
        if getattr(sys, "frozen", False):
            import os
            print("\\n" + "═"*60)
            print("  Ripen has stopped. (EXE Mode)")
            # Use Windows native pause command - much more reliable than input()
            os.system("pause")

if __name__ == "__main__":
    run()
    # One more check just in case run() returns prematurely
    import sys
    if getattr(sys, "frozen", False):
        import os
        os.system("pause")
"""
    with open(entry_point, "w", encoding="utf-8") as f:
        f.write(entry_content.strip())

    # 2. Prepare PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=ripen",
        "--onefile",
        "--console",
        f"--icon={base_dir / 'logo.ico'}",
        "--clean",
        # Metadata is required by FastMCP to detect its own version
        "--copy-metadata=fastmcp",
        "--copy-metadata=ripen",
        "--hidden-import=ripen.api.server",
        "--hidden-import=ripen.cli.init",
        "--hidden-import=ripen.cli.shortcut",
        "--hidden-import=ripen.cli.admin_cli",
        "--hidden-import=fastembed",
        "--hidden-import=faiss",
        "--hidden-import=google.genai",
        f"--add-data=src/ripen;ripen",
        str(entry_point),
    ]

    print(f"Running command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print("\n" + "=" * 50)
        print("Build Successful!")
        print(f"EXE Location: {dist_dir / 'ripen.exe'}")
        print("=" * 50)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    finally:
        # Cleanup entry point
        if entry_point.exists():
            os.remove(entry_point)


if __name__ == "__main__":
    build()
