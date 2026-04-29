import pytest

from shared_memory.infra.database import init_db
from shared_memory.ops.health import check_db_health, get_comprehensive_diagnostics


@pytest.mark.asyncio
async def test_check_db_health():
    """Verify health check returns healthy for initialized DB."""
    await init_db(force=True)
    status = await check_db_health()
    assert status["status"] == "healthy"
    assert "entities_count" in status


@pytest.mark.asyncio
async def test_check_diagnostics():
    """Verify diagnostics passes for clean system."""
    await init_db(force=True)
    report = await get_comprehensive_diagnostics()
    assert report["db_status"] == "healthy"
    assert report["disk_status"] == "healthy"
