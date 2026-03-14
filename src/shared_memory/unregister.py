import os
import json
import argparse
import hashlib
from pathlib import Path

def get_config_paths():
    appdata = os.environ.get("APPDATA")
    if not appdata: return {}
    return {
        "Claude Desktop": Path(appdata) / "Claude" / "claude_desktop_config.json",
        "Cursor (Roo Code/Cline)": Path(appdata) / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Roo Code/Cline)": Path(appdata) / "antigravity" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Central)": Path("C:/Users/saiha/.gemini/antigravity/mcp_config.json")
    }

def get_prompt_files():
    cwd = Path.cwd()
    return [
        Path("C:/Users/saiha/.gemini/GEMINI.md"),
        cwd / ".gemini" / "GEMINI.md",
        cwd / ".cursorrules",
        cwd / ".clinerules"
    ]

def unregister_mcp(dry_run=False, isolate=False):
    config_paths = get_config_paths()
    cwd = os.getcwd()
    server_name = "SharedMemoryServer"
    if isolate:
        path_hash = hashlib.md5(cwd.encode('utf-8')).hexdigest()[:8]
        server_name = f"SharedMemoryServer_{path_hash}"

    print(f"--- MCP Unregistration (Dry Run: {dry_run}) ---")
    for name, path in config_paths.items():
        if not path.exists(): continue
        try:
            with open(path, 'r', encoding='utf-8') as f: config = json.load(f)
            if "mcpServers" in config and server_name in config["mcpServers"]:
                del config["mcpServers"][server_name]
                if not dry_run:
                    with open(path, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2)
                print(f"  [SUCCESS] Removed {server_name} from {name}")
        except Exception as e: print(f"  [ERROR] Failed {name}: {e}")

    print(f"\n--- Prompt Instruction Cleanup ---")
    for p in get_prompt_files():
        if not p.exists(): continue
        try:
            content = p.read_text(encoding='utf-8')
            if "# SHARED MEMORY SERVER INSTRUCTION" in content:
                # Basic removal logic: remove everything from the marker to the end of that block
                lines = content.splitlines()
                new_lines = []
                skipping = False
                for line in lines:
                    if "# SHARED MEMORY SERVER INSTRUCTION" in line:
                        skipping = True
                        continue
                    if skipping and line.strip() == "": # Stop skipping at next empty line or specific marker
                        # For now, let's just use a simple marker-based removal or pattern
                        pass
                    if not skipping:
                        new_lines.append(line)
                
                # Better approach: If we know the instructions are at the end, we can just trim.
                # Since our register.py appends to the end, we'll look for the marker.
                idx = content.find("# SHARED MEMORY SERVER INSTRUCTION")
                new_content = content[:idx].strip()
                
                if not dry_run:
                    p.write_text(new_content, encoding='utf-8')
                print(f"  [SUCCESS] Cleaned {p.name}")
        except Exception as e: print(f"  [ERROR] Failed {p.name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unregister SharedMemoryServer.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--isolate", action="store_true")
    args = parser.parse_args()
    unregister_mcp(dry_run=args.dry_run, isolate=args.isolate)
