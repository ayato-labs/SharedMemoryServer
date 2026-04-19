import argparse
import hashlib
import json
import os
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
    }


def get_prompt_files():
    """Identify system prompt files to clean up."""
    cwd = Path.cwd()
    home = Path.home()
    return [
        home / ".gemini" / "GEMINI.md",
        cwd / ".gemini" / "GEMINI.md",
        cwd / ".cursorrules",
        cwd / ".clinerules",
    ]


def unregister_mcp(dry_run=False, isolate=False):
    config_paths = get_config_paths()
    cwd = os.getcwd()
    server_name = "SharedMemoryServer"
    if isolate:
        path_hash = hashlib.md5(cwd.encode("utf-8")).hexdigest()[:8]
        server_name = f"SharedMemoryServer_{path_hash}"

    print(f"--- MCP Unregistration (Dry Run: {dry_run}) ---")
    for name, path in config_paths.items():
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                config = json.load(f)

            updated = False
            # Standard mcpServers
            if "mcpServers" in config and server_name in config["mcpServers"]:
                del config["mcpServers"][server_name]
                updated = True

            # Native Cursor
            if "cursor.mcpServers" in config and server_name in config["cursor.mcpServers"]:
                del config["cursor.mcpServers"][server_name]
                updated = True

            if updated:
                if not dry_run:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=2)
                print(f"  [SUCCESS] Removed {server_name} from {name}")
        except Exception as e:
            import sys

            sys.stderr.write(f"  [ERROR] Failed {name}: {e}\n")

    print("\n--- Prompt Instruction Cleanup ---")
    for p in get_prompt_files():
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8")
            if "# SHARED MEMORY SERVER INSTRUCTION" in content:
                # Basic removal logic: locate marker and trim
                idx = content.find("# SHARED MEMORY SERVER INSTRUCTION")
                new_content = content[:idx].strip()

                if not dry_run:
                    p.write_text(new_content, encoding="utf-8")
                print(f"  [SUCCESS] Cleaned {p.name}")
        except Exception as e:
            import sys

            sys.stderr.write(f"  [ERROR] Failed {p.name}: {e}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unregister SharedMemoryServer.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--isolate", action="store_true")
    args = parser.parse_args()
    unregister_mcp(dry_run=args.dry_run, isolate=args.isolate)
