import os
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List

def get_config_paths():
    """Detect potential MCP configuration file paths on Windows."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return {}

    return {
        "Claude Desktop": Path(appdata) / "Claude" / "claude_desktop_config.json",
        "Cursor (Roo Code/Cline)": Path(appdata) / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Roo Code/Cline)": Path(appdata) / "antigravity" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Central)": Path("C:/Users/saiha/.gemini/antigravity/mcp_config.json"),
        "Cursor (Global)": Path(appdata) / "Cursor" / "User" / "settings.json"
    }

def get_prompt_files() -> List[Path]:
    """Identify system prompt files to inject instructions into."""
    cwd = Path.cwd()
    
    paths = [
        Path("C:/Users/saiha/.gemini/GEMINI.md"), # Global Antigravity
        cwd / ".gemini" / "GEMINI.md",             # Local Antigravity
        cwd / ".cursorrules",                     # Local Cursor
        cwd / ".clinerules"                        # Local Cline/Roo
    ]
    return paths

def get_server_command():
    """Get the absolute command to run the server."""
    cwd = os.getcwd()
    venv_python = os.path.join(cwd, ".venv", "Scripts", "python.exe")
    server_script = os.path.join(cwd, "src", "shared_memory", "server.py")
    
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    return [venv_python, server_script]

SHARED_MEMORY_PROMPT = """
# SHARED MEMORY SERVER INSTRUCTION
You have access to SharedMemoryServer MCP.
- Use it to maintain project-wide entities, relations, and factual observations.
- Always call `read_memory(query=...)` at the start of a task to gather relevant context.
- Use `save_memory` to persist important architectural roles, technical decisions, and multi-step progress.
"""

def register_mcp(dry_run=False):
    config_paths = get_config_paths()
    cmd = get_server_command()
    
    mcp_config = {
        "command": cmd[0],
        "args": cmd[1:],
        "env": {
            "MEMORY_DB_PATH": os.path.join(os.getcwd(), "shared_memory.db"),
            "MEMORY_BANK_DIR": os.path.join(os.getcwd(), "memory-bank")
        }
    }

    print(f"--- MCP Registration (Dry Run: {dry_run}) ---")
    
    for name, path in config_paths.items():
        if not path.parent.exists():
            continue

        if not path.exists() and name != "Antigravity (Central)":
            print(f"  [SKIP] {name}: {path} not found.")
            continue
            
        try:
            config = {}
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # Determine where to put the MCP config based on file type
            if any(x in str(path) for x in ["mcp_config.json", "cline_mcp_settings.json", "claude_desktop_config.json"]):
                if "mcpServers" not in config:
                    config["mcpServers"] = {}
                config["mcpServers"]["SharedMemoryServer"] = mcp_config
            elif "settings.json" in str(path):
                print(f"  [SKIP] Global Cursor settings.json is complex. Please register manually via UI if needed.")
                continue
            
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                print(f"  [SUCCESS] Updated {name}")
            else:
                print(f"  [DRY RUN] Would update {name}")
                
        except Exception as e:
            print(f"  [ERROR] Failed to update {name}: {e}")

    print(f"\n--- System Prompt Integration (Dry Run: {dry_run}) ---")
    prompt_files = get_prompt_files()
    for p in prompt_files:
        if not p.parent.exists() and not dry_run:
            continue
            
        try:
            content = ""
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            if "SHARED_MEMORY_SERVER_INSTRUCTION" in content:
                print(f"  [SKIP] {p.name}: Instructions already present.")
                continue
                
            new_content = content.strip() + "\n\n" + SHARED_MEMORY_PROMPT.strip() + "\n"
            
            if not dry_run:
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"  [SUCCESS] Updated {p.name}")
            else:
                print(f"  [DRY RUN] Would update {p.name}")
        except Exception as e:
            print(f"  [ERROR] Failed to update {p.name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Register SharedMemoryServer as an MCP tool and update system prompts.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes.")
    args = parser.parse_args()
    
    register_mcp(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
