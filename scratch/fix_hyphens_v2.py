import os
from pathlib import Path

def fix_hyphens():
    root = Path('c:/Users/saiha/My_Service/programing/MCP/SharedMemoryServer')
    # Targeted files
    targets = [
        root / 'bin' / 'sse.bat',
        root / 'bin' / 'stdio.bat',
        root / 'bin' / 'register.bat',
        root / 'bin' / 'admin.bat',
        root / 'bin' / 'test.bat',
        root / 'bin' / 'setup_team_hub.bat',
        root / 'pyproject.toml',
        root / 'README.md',
    ]
    
    for p in targets:
        if p.exists():
            content = p.read_text(encoding='utf-8')
            new_content = content.replace('shared-memory', 'ripen')
            if content != new_content:
                p.write_text(new_content, encoding='utf-8')
                print(f"Fixed: {p.name}")

if __name__ == "__main__":
    fix_hyphens()
