import os
import re

def replace_in_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return
    
    new_content = content.replace('shared-memory', 'ripen')
    
    if content != new_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")

def main():
    root_dir = 'c:\\Users\\saiha\\My_Service\\programing\\MCP\\SharedMemoryServer'
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py') or file.endswith('.bat') or file.endswith('.md') or file.endswith('.json'):
                replace_in_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
