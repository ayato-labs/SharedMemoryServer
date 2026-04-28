from shared_memory.utils import calculate_importance, mask_sensitive_data, sanitize_filename


def test_calculate_importance_basic():
    # Frequency should increase importance
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).isoformat()
    
    freq_1 = calculate_importance(1, now)
    freq_10 = calculate_importance(10, now)
    assert freq_10 > freq_1
    
    # Recency should increase importance (older is less important)
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    freq_1_recent = calculate_importance(1, now)
    freq_1_old = calculate_importance(1, old)
    assert freq_1_recent > freq_1_old
    
    # Range check - importance is not strictly bounded [0, 1] anymore due to log1p
    assert calculate_importance(0, now) >= 0
    assert calculate_importance(100, now) > 0

def test_sanitize_filename():
    assert sanitize_filename("Hello World.md") == "hello_world.md"
    # Note: implementation strips ext and appends .md
    assert sanitize_filename("  spaces  .txt") == "spaces.md"
    assert sanitize_filename("Path/To\\File.md") == "file.md" # os.path.basename handles this
    assert sanitize_filename("UPPER.MD") == "upper.md"
    assert sanitize_filename("!@#$%^&*().md") == "_.md"

def test_mask_sensitive_data():
    # Google API Key is AIzaSy + 33 chars = 39 total
    long_key = "AIzaSy" + "A" * 33
    text = f"My API key is {long_key} and secret is sk-{'1'*20}"
    masked = mask_sensitive_data(text)
    
    assert long_key not in masked
    assert "sk-" not in masked
    assert "_MASKED]" in masked
    
    # Verify it doesn't mask normal text
    normal = "The quick brown fox"
    assert mask_sensitive_data(normal) == normal

def test_mask_sensitive_data_in_json():
    long_key = "AIzaSy" + "B" * 33
    data = {"api_key": long_key, "normal": "value"}
    import json
    text = json.dumps(data)
    masked = mask_sensitive_data(text)
    
    assert "_MASKED]" in masked
    assert "value" in masked
    assert long_key not in masked
