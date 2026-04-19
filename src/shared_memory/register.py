import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def get_config_paths():
    """Detect potential MCP configuration file paths on Windows."""
    appdata = os.environ.get("APPDATA")
    home = Path.home()
    if not appdata:
        return {}

    return {
        "Claude Desktop": Path(appdata) / "Claude" / "claude_desktop_config.json",
        "Cursor (Roo Code/Cline)": Path(appdata)
        / "Cursor"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json",
        "Antigravity (Roo Code/Cline)": Path(appdata)
        / "antigravity"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json",
        "Antigravity (Central)": home / ".gemini" / "antigravity" / "mcp_config.json",
        "Cursor (Global)": Path(appdata) / "Cursor" / "User" / "settings.json",
        "Cloud Code (User)": Path(appdata) / "Code" / "User" / "mcp.json",
        "Gemini CLI": home / ".gemini" / "settings.json",
    }


def get_prompt_files() -> list[Path]:
    """Identify system prompt files to inject instructions into."""
    cwd = Path.cwd()
    home = Path.home()

    paths = [
        home / ".gemini" / "GEMINI.md",  # Global Antigravity
        cwd / ".gemini" / "GEMINI.md",  # Local Antigravity
        cwd / ".cursorrules",  # Local Cursor
        cwd / ".clinerules",  # Local Cline/Roo
    ]
    return paths


def get_server_command():
    """Get the absolute command to run the server."""
    cwd = os.getcwd()

    # Check if we are running as a frozen executable (PyInstaller)
    if getattr(sys, "frozen", False):
        # Bundled executable path
        return [sys.executable]

    venv_python = os.path.join(cwd, ".venv", "Scripts", "python.exe")
    server_script = os.path.join(cwd, "src", "shared_memory", "server.py")

    if not os.path.exists(venv_python):
        venv_python = sys.executable

    return [venv_python, server_script]


SHARED_MEMORY_PROMPT = """
# SHARED MEMORY SERVER INSTRUCTION
You have access to SharedMemoryServer MCP.
- Use it to maintain project-wide entities, relations, and factual observations.
- Always call `read_memory(query=...)` at the start of a task to
  gather relevant context.
- Use `save_memory` to persist important architectural roles,
  technical decisions, and multi-step progress.
"""


def register_single_mcp(config_paths, server_name, mcp_config, dry_run=False):
    """Register a single MCP server in all detected configuration files."""
    print(f"\n--- Registering {server_name} (Dry Run: {dry_run}) ---")
    for name, path in config_paths.items():
        if not path.parent.exists():
            continue

        if not path.exists() and name not in [
            "Antigravity (Central)",
            "Cloud Code (User)",
            "Cursor (Global)",
            "Gemini CLI",
        ]:
            print(f"  [SKIP] {name}: {path} not found.")
            continue

        try:
            config = {}
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        config = json.load(f)
                except json.JSONDecodeError:
                    print(f"  [WARN] {name}: Failed to parse {path}. Skipping.")
                    continue

            # Determine where to put the MCP config based on file type
            if any(
                x in str(path)
                for x in [
                    "mcp_config.json",
                    "cline_mcp_settings.json",
                    "claude_desktop_config.json",
                    "mcp.json",
                    "settings.json",
                ]
            ):
                if "Cursor" in name and "settings.json" in str(path):
                    # Native Cursor Registration
                    if "cursor.mcpServers" not in config:
                        config["cursor.mcpServers"] = {}
                    config["cursor.mcpServers"][server_name] = {
                        "type": "command",
                        "command": (
                            f'"{mcp_config["command"]}" {" ".join(mcp_config["args"])}'
                        ).strip(),
                        "env": mcp_config["env"],
                    }
                else:
                    # Standard mcpServers
                    if "mcpServers" not in config:
                        config["mcpServers"] = {}
                    config["mcpServers"][server_name] = mcp_config
            else:
                continue

            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print(f"  [SUCCESS] Updated {name} for {server_name}")
            else:
                print(f"  [DRY RUN] Would update {name} for {server_name}")

        except Exception as e:
            sys.stderr.write(f"  [ERROR] Failed to update {name} for {server_name}: {e}\n")


def register_mcp(dry_run=False, isolate=False):
    config_paths = get_config_paths()
    cwd = os.getcwd()

    # 1. SharedMemoryServer Config (Zero-Config Approach)
    # The server will now automatically resolve paths based on current project root.
    server_name = "SharedMemoryServer"

    if isolate:
        path_hash = hashlib.md5(cwd.encode("utf-8")).hexdigest()[:8]
        server_name = f"SharedMemoryServer_{path_hash}"

    sm_path_str = str(Path(cwd)).replace("\\", "/")
    sm_mcp_config = {
        "command": "uv",
        "args": [
            "run",
            "--project",
            sm_path_str,
            "--no-sync",
            "python",
            f"{sm_path_str}/src/shared_memory/server.py",
        ],
        "env": {
            # Zero-Config: Paths are resolved autonomously by the server logic
        },
    }

    # BYOK Logic
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key and not dry_run:
        print("\n--- Google / Gemini API Key (BYOK) ---")
        api_key = input(
            "Enter your Google/Gemini API Key (leave empty to skip semantic search): "
        ).strip()

    if api_key:
        sm_mcp_config["env"]["GOOGLE_API_KEY"] = api_key

    register_single_mcp(config_paths, server_name, sm_mcp_config, dry_run=dry_run)

    # 2. LogicHive Config (Auto-detection)
    mcp_parent = Path(cwd).parent
    logichive_path = mcp_parent / "LogicHive"
    if logichive_path.exists():
        lh_path_str = str(logichive_path).replace("\\", "/")
        lh_src_path_str = str(logichive_path / "src").replace("\\", "/")
        logichive_mcp_config = {
            "command": "uv",
            "args": [
                "run",
                "--project",
                lh_path_str,
                "--no-sync",
                "python",
                f"{lh_src_path_str}/mcp_server.py",
            ],
            "env": {"PYTHONPATH": f"{lh_path_str};{lh_src_path_str}"},
        }
        register_single_mcp(config_paths, "logic-hive", logichive_mcp_config, dry_run=dry_run)

    print(f"\n--- System Prompt Integration (Dry Run: {dry_run}) ---")
    prompt_files = get_prompt_files()
    for p in prompt_files:
        if not p.parent.exists() and not dry_run:
            continue

        try:
            content = ""
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    content = f.read()

            if "SHARED_MEMORY_SERVER_INSTRUCTION" in content:
                print(f"  [SKIP] {p.name}: Instructions already present.")
                continue

            new_content = content.strip() + "\n\n" + SHARED_MEMORY_PROMPT.strip() + "\n"

            if not dry_run:
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"  [SUCCESS] Updated {p.name}")
            else:
                print(f"  [DRY RUN] Would update {p.name}")
        except Exception as e:
            sys.stderr.write(f"  [ERROR] Failed to update {p.name}: {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description=("Register SharedMemoryServer as an MCP tool and update system prompts.")
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help=("Register a unique instance for the current project to avoid shared memory."),
    )
    args = parser.parse_args()

    register_mcp(dry_run=args.dry_run, isolate=args.isolate)


if __name__ == "__main__":
    main()
