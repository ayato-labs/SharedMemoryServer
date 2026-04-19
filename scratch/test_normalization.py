
from shared_memory.logic import normalize_bank_files

def test_normalization():
    # 1. Standard list of dicts
    input1 = [{"filename": "test1.md", "content": "hello"}]
    res1 = normalize_bank_files(input1)
    assert res1 == {"test1.md": "hello"}
    print("Test 1 passed")

    # 2. List of dicts with synonyms (name/text)
    input2 = [{"name": "test2.md", "text": "world"}]
    res2 = normalize_bank_files(input2)
    assert res2 == {"test2.md": "world"}
    print("Test 2 passed")

    # 3. List of single-entry dicts
    input3 = [{"test3.md": "content3"}]
    res3 = normalize_bank_files(input3)
    assert res3 == {"test3.md": "content3"}
    print("Test 3 passed")

    # 4. Single dict object
    input4 = {"filename": "test4.md", "content": "direct"}
    res4 = normalize_bank_files(input4)
    assert res4 == {"test4.md": "direct"}
    print("Test 4 passed")

    # 5. Missing filename (auto-generation)
    input5 = [{"content": "no name"}]
    res5 = normalize_bank_files(input5)
    assert "derived_knowledge_0.md" in res5
    print("Test 5 passed")

if __name__ == "__main__":
    test_normalization()
    print("\nAll normalization tests PASSED!")
