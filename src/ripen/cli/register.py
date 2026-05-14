import argparse
import json
import os
import sys
from pathlib import Path
from ripen.common.utils import get_logger, safe_main_executor


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


def register_mcp(transport="stdio", port=8377, hub_url=None):
    """
    Registers this Ripen instance as an MCP server in external configuration files.
    """
    config_paths = get_config_paths()
    cwd = os.getcwd()
    python_exe = sys.executable

    # Detect if we are in a dev environment (running from src) or installed
    if os.path.exists(os.path.join(cwd, "src", "ripen")):
        # Dev mode
        args = [python_exe, "-m", "ripen.api.server"]
        env_pythonpath = os.path.join(cwd, "src")
    else:
        # Installed mode: use the 'ripen' entry point directly
        # However, for MCP reliability, sometimes the full python path is better
        args = ["ripen"]
        env_pythonpath = ""

    if hub_url:
        # Client mode: connect to remote hub
        args.append("--sse")
        args.append("--host")
        args.append(hub_url)
    elif transport == "sse":
        args.append("--sse")
        args.append("--port")
        args.append(str(port))

    server_config = {
        "command": args[0],
        "args": args[1:],
        "env": {},
    }

    if env_pythonpath:
        server_config["env"]["PYTHONPATH"] = env_pythonpath

    # Special handling for Antigravity (shared memory context)
    server_config["env"]["SHARED_MEMORY_HOME"] = os.path.join(Path.home(), ".ripen")

    print(f"--- MCP Registration ---")
    for name, path in config_paths.items():
        if not path.exists():
            continue

        try:
            # Create directory if it doesn't exist (e.g. Antigravity central)
            path.parent.mkdir(parents=True, exist_ok=True)

            if path.exists():
                with open(path, encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = {}

            # Handle different config formats
            if "mcpServers" not in config:
                config["mcpServers"] = {}

            # Unique server name per project directory to avoid collisions
            import hashlib

            path_hash = hashlib.md5(cwd.encode("utf-8")).hexdigest()[:8]
            server_name = f"Ripen_{path_hash}"

            config["mcpServers"][server_name] = server_config

            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            print(f"  [SUCCESS] Registered '{server_name}' in {name}")
        except Exception as e:
            print(f"  [ERROR] Failed to update {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Register Ripen with IDEs.")
    parser.add_argument("--sse", action="store_true", help="Register as SSE client")
    parser.add_argument("--port", type=int, default=8377, help="SSE Port")
    parser.add_argument("--hub", help="Remote Hub URL")

    args = parser.parse_args()

    transport = "sse" if args.sse or args.hub else "stdio"
    register_mcp(transport=transport, port=args.port, hub_url=args.hub)


if __name__ == "__main__":
    safe_main_executor(main)()
