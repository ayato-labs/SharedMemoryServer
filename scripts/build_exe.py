import os
import subprocess
import sys
from pathlib import Path


def kill_existing_process(target_name):
    """Kills any running process with the target name to release file locks."""
    if sys.platform == "win32":
        print(f"Checking for running {target_name}.exe processes...")
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", f"{target_name}.exe", "/T"], capture_output=True, check=False
            )
        except Exception:
            pass

def generate_entry_point(base_dir: Path, target: str) -> Path:
    entry_point = base_dir / f"ripen_launcher_{target}.py"
    
    if target == "hub":
        entry_content = """
import sys
import multiprocessing
import traceback
from ripen.api.server import main as server_main

def run():
    multiprocessing.freeze_support()
    try:
        server_main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\\n\\033[1;31m[FATAL ERROR]\\033[0m {e}")
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            import os
            os.system("pause")

if __name__ == "__main__":
    run()
"""
    elif target == "admin":
        entry_content = """
import sys
import multiprocessing
import traceback
from ripen.cli.init import main as init_main
from ripen.cli.admin_cli import main as admin_main

def run():
    multiprocessing.freeze_support()
    try:
        if len(sys.argv) > 1 and sys.argv[1].lower() == "init":
            sys.argv.pop(1)
            init_main()
        else:
            admin_main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\\n\\033[1;31m[FATAL ERROR]\\033[0m {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run()
"""
    with open(entry_point, "w", encoding="utf-8") as f:
        f.write(entry_content.strip())
    
    return entry_point

def build_target(target: str, base_dir: Path):
    target_name = f"ripen-{target}"
    print(f"\\n{'='*50}\\nBuilding {target_name}.exe...\\n{'='*50}")
    
    kill_existing_process(target_name)
    entry_point = generate_entry_point(base_dir, target)
    
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        f"--name={target_name}",
        "--onefile",
        "--console",
        f"--icon={base_dir / 'logo.ico'}",
        "--clean",
        "--copy-metadata=fastmcp",
        "--copy-metadata=ripen",
        "--add-data=src/ripen;ripen",
    ]
    
    # Target specific hidden imports
    if target == "hub":
        cmd.extend([
            "--hidden-import=ripen.api.server",
            "--hidden-import=fastembed",
            "--hidden-import=faiss",
            "--hidden-import=google.genai",
            "--hidden-import=uvicorn"
        ])
    elif target == "admin":
        cmd.extend([
            "--hidden-import=ripen.cli.init",
            "--hidden-import=ripen.cli.admin_cli",
            "--hidden-import=ripen.cli.shortcut"
        ])

    cmd.append(str(entry_point))
    
    try:
        subprocess.run(cmd, check=True)
        print(f"\\nBuilt {target_name}.exe successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Build failed for {target_name} with exit code {e.returncode}")
        sys.exit(e.returncode)
    finally:
        if entry_point.exists():
            os.remove(entry_point)

def build():
    valid_targets = ["hub", "admin", "all"]
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    
    if target not in valid_targets:
        print(f"Invalid target: {target}. Valid targets: {valid_targets}")
        sys.exit(1)
        
    base_dir = Path(__file__).parent.parent.absolute()
    
    targets_to_build = ["hub", "admin"] if target == "all" else [target]
    
    for t in targets_to_build:
        build_target(t, base_dir)

if __name__ == "__main__":
    build()

