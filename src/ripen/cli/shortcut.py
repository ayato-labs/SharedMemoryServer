import os
import subprocess
from pathlib import Path

from ripen.common.utils import get_logger

logger = get_logger("shortcut")


def create_windows_shortcut(
    target_path: str,
    shortcut_name: str,
    description: str = "Ripen Knowledge Hub",
    arguments: str = "",
):
    """
    Creates a Windows desktop shortcut (.lnk) using PowerShell.
    """
    try:
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
        shortcut_path = desktop / f"{shortcut_name}.lnk"

        # Escape single quotes for PowerShell
        target_path_esc = target_path.replace("'", "''")
        shortcut_path_esc = str(shortcut_path).replace("'", "''")
        args_esc = arguments.replace("'", "''")

        # Use a single-line PowerShell command joined by semicolons
        ps_command = (
            f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path_esc}'); "
            f"$s.TargetPath = '{target_path_esc}'; "
            f"$s.Arguments = '{args_esc}'; "
            f"$s.Description = '{description}'; "
            f"$s.Save()"
        )

        # Run with ExecutionPolicy Bypass to avoid restrictions
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            check=True,
            capture_output=True,
            text=True,
        )
        return str(shortcut_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"PowerShell failed to create shortcut: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Failed to create shortcut: {e}")
        return None


def create_launcher_bat(ripen_home: Path) -> Path:
    """
    Creates a launcher for the hub.
    If running as a frozen EXE, returns the path to the EXE itself.
    Otherwise, creates a .bat file that launches the python module.
    """
    import sys

    if getattr(sys, "frozen", False):
        # We are running as an EXE
        exe_path = Path(sys.executable)
        return exe_path

    # Standard python execution
    bat_path = ripen_home / "ripen-launcher.bat"
    python_exe = sys.executable

    # Use the absolute path to python to ensure it works outside the venv
    # We use %* to pass any arguments from the shortcut to the python command
    content = f'@echo off\ntitle Ripen Hub\n"{python_exe}" -m ripen.api.server %*\npause'

    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(content)

    return bat_path
