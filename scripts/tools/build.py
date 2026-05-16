import os
import shutil
import subprocess
import sys


def run_command(cmd):
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, shell=True, check=False)
    if result.returncode != 0:
        print(f"Error executing command: {result.returncode}")
        sys.exit(1)


def build():
    # Ensure dist and build directories are clean
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    print("--- Building Ripen Hub ---")
    run_command(
        [
            "pyinstaller",
            "--onefile",
            "--name",
            "Ripen-Hub",
            "--clean",
            "src/ripen/api/server.py",
        ]
    )

    print("\n--- Build Complete ---")
    print("Executables are in the 'dist' directory.")


if __name__ == "__main__":
    # Check if pyinstaller is installed
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Installing...")
        run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])

    build()
