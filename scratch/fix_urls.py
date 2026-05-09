import os
from pathlib import Path

def fix_urls():
    root = Path('c:/Users/saiha/My_Service/programing/MCP/SharedMemoryServer')
    old_url = "https://github.com/ayato-labs/ripen"
    new_url = "https://github.com/ayato-labs/ripen"
    
    # Also fix lowercase/mixed case just in case
    old_url_lower = old_url.lower()
    
    for p in root.rglob('*'):
        if p.is_dir() and (p.name == '.git' or p.name == '.venv' or p.name == '__pycache__'):
            continue
        if p.is_file() and p.suffix in ['.md', '.toml', '.json', '.bat', '.py', '.sh']:
            try:
                content = p.read_text(encoding='utf-8')
                new_content = content.replace(old_url, new_url)
                # Case insensitive check if needed, but let's stick to exact for now
                
                if content != new_content:
                    p.write_text(new_content, encoding='utf-8')
                    print(f"Updated URL in: {p.relative_to(root)}")
            except:
                pass

if __name__ == "__main__":
    fix_urls()
