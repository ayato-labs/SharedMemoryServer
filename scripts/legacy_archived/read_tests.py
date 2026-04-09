with open("test_results.txt", encoding="utf-16le") as f:
    lines = f.readlines()
    for line in lines:
        if "FAIL" in line or "Error" in line:
            print(line.strip())
        if "_ _ _ _" in line or ">>" in line:
            # Print context
            idx = lines.index(line)
            for i in range(idx, min(idx + 10, len(lines))):
                print(lines[i].strip())
