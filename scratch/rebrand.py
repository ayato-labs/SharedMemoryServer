import os
import re

def replace_in_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='cp932') as f:
                content = f.read()
        except:
            print(f"Skipping (decode error): {file_path}")
            return
    
    # Replace module name
    new_content = re.sub(r'\bshared_memory\b', 'ripen', content)
    
    # Replace display name
    new_content = new_content.replace('Ripen', 'Ripen')
    
    if content != new_content:
        # Use utf-8 for writing back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")

def main():
    root_dir = 'c:\\Users\\saiha\\My_Service\\programing\\MCP\\Ripen'
    for root, dirs, files in os.walk(root_dir):
        if '.git' in dirs:
            dirs.remove('.git')
        if '.venv' in dirs:
            dirs.remove('.venv')
        if '.clinerules' in files:
            replace_in_file(os.path.join(root, '.clinerules'))
        if '.cursorrules' in files:
            replace_in_file(os.path.join(root, '.cursorrules'))
        
        for file in files:
            if file.endswith('.py') or file.endswith('.md') or file.endswith('.yml') or file.endswith('.bat') or file.endswith('.json'):
                file_path = os.path.join(root, file)
                replace_in_file(file_path)

if __name__ == "__main__":
    main()
