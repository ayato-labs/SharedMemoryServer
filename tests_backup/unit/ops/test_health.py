from unittest.mock import MagicMock, patch

import pytest

from ripen.infra.database import init_db
from ripen.ops.health import check_db_health, get_comprehensive_diagnostics


@pytest.mark.asyncio
async def test_check_db_health():
    """Verify health check returns healthy for initialized DB."""
    await init_db(force=True)
    status = await check_db_health()
    assert status["status"] == "healthy"
    assert "entities_count" in status


@pytest.mark.asyncio
async def test_check_diagnostics(_fake_llm):
    """Verify diagnostics passes for clean system."""
    await init_db(force=True)

    # Mock disk usage to ensure 'healthy' status
    mock_usage = MagicMock()
    mock_usage.total = 1000
    mock_usage.used = 100
    mock_usage.free = 900

    with patch("shutil.disk_usage", return_value=mock_usage):
        report = await get_comprehensive_diagnostics()
        assert report["db_status"] == "healthy"
        assert report["disk_status"] == "healthy"
