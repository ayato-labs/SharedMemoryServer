import os
import re

pattern = re.compile(r"except.*:\s*pass", re.MULTILINE)


def find_swallowed_errors(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                    if pattern.search(content):
                        print(f"FOUND in {path}")


if __name__ == "__main__":
    find_swallowed_errors("src")
    find_swallowed_errors("tests")
