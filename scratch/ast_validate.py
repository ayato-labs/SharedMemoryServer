import ast
import os


def find_syntax_errors(root_dir):
    for root, _dirs, files in os.walk(root_dir):
        if ".venv" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, encoding="utf-8") as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    print(f"SYNTAX ERROR in {path} at line {e.lineno}, col {e.offset}: {e.msg}")
                    with open(path, encoding="utf-8") as f:
                        lines = f.readlines()
                        if e.lineno <= len(lines):
                            print(f"  Line {e.lineno}: {lines[e.lineno - 1].strip()}")
                except Exception as e:
                    print(f"ERROR processing {path}: {e}")


if __name__ == "__main__":
    find_syntax_errors("src")
    find_syntax_errors("scripts")
    find_syntax_errors("tests")
