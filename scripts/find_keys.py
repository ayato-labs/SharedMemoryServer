import json
import os

def list_keys_recursive(data, prefix=''):
    if isinstance(data, dict):
        for k, v in data.items():
            curr = f"{prefix}.{k}" if prefix else k
            print(curr)
            list_keys_recursive(v, curr)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            list_keys_recursive(v, f"{prefix}[{i}]")

path = os.path.expanduser("~/.gemini/settings.json")
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        list_keys_recursive(data)
else:
    print(f"File not found: {path}")
