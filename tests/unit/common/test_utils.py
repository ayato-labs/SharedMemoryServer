import os

from shared_memory.common import utils


def test_mask_sensitive_data():
    """Verify masking logic for logs."""
    # AIzaSy + 33 chars = 39 chars total
    text = "My key is AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P678."
    masked = utils.mask_sensitive_data(text)
    assert "[GOOGLE_API_KEY_MASKED]" in masked
    assert "AIzaSy" not in masked


def test_safe_path_join():
    """Verify safe path joining to prevent traversal."""
    base = os.path.abspath("/tmp/bank")
    # basename strips leading components
    result = utils.safe_path_join(base, "../etc/passwd")
    assert "passwd" in result
    assert "etc" not in result


def test_calculate_importance():
    """Verify importance score calculation."""
    # (access_count: int, last_accessed: str) -> float
    score1 = utils.calculate_importance(1, "2023-01-01T00:00:00")
    score2 = utils.calculate_importance(100, "2023-01-01T00:00:00")
    assert score2 > score1
