from datetime import UTC, datetime, timedelta

from shared_memory.common.utils import (
    calculate_importance,
    mask_sensitive_data,
    sanitize_filename,
)


def test_calculate_importance_basic():
    """Verify that importance decreases over time and increases with frequency."""
    now = datetime.now(UTC).isoformat()
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    last_month = (datetime.now(UTC) - timedelta(days=30)).isoformat()

    # 1. Frequency effect
    score_high_freq = calculate_importance(10, now)
    score_low_freq = calculate_importance(1, now)
    assert score_high_freq > score_low_freq

    # 2. Recency effect (Time decay)
    score_now = calculate_importance(5, now)
    score_yesterday = calculate_importance(5, yesterday)
    score_old = calculate_importance(5, last_month)

    assert score_now > score_yesterday > score_old
    # Half-life is 30 days, so score_old should be roughly half of score_now (ignoring log1p diff)
    # Actually freq_score is the same, so it's purely decay.
    # decay = exp(-30/30) = exp(-1) approx 0.36
    assert score_old < score_now * 0.4


def test_calculate_importance_error_handling():
    """Verify it returns 0.0 on malformed input instead of crashing."""
    assert calculate_importance(10, "invalid-date") == 0.0
    assert (
        calculate_importance(-1, "2024-01-01") >= 0.0
    )  # log1p(-1) is undefined, should be handled


def test_sanitize_filename():
    """Verify path traversal prevention and character normalization."""
    assert sanitize_filename("../test.txt") == "test.md"
    assert sanitize_filename("Complex Name!!! 123.md") == "complex_name_123.md"
    assert sanitize_filename(".../.hidden") == "hidden.md"
    assert sanitize_filename("...") == "unnamed_entity.md"


def test_mask_sensitive_data():
    """Verify that API keys and emails are masked."""
    # Google API keys are AIzaSy + 33 chars = 39 chars total
    # My previous key was too short (32 chars after AIzaSy)
    key = "AIzaSy" + "A" * 33
    raw = f"My key is {key} and email is test@example.com"
    masked = mask_sensitive_data(raw)
    assert "[GOOGLE_API_KEY_MASKED]" in masked
    assert "[EMAIL_MASKED]" in masked
    assert "AIzaSy" not in masked
    assert "test@example.com" not in masked


def test_log_error_with_braces():
    """Verify that log_error doesn't crash when exception string contains braces."""
    from shared_memory.common.utils import log_error

    # This string caused KeyError in loguru if handled improperly with f-strings
    braces_error = ValueError("{'error': {'code': 500, 'message': 'Internal error'}}")

    # Should not raise KeyError
    log_error("Testing braces error", braces_error)
    log_error("Testing braces msg with {braces}")
