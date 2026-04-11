import pytest
from shared_memory import logic
from shared_memory.database import init_db
from shared_memory.thought_logic import init_thoughts_db

@pytest.mark.asyncio
async def test_admin_get_value_report_logic_flow():
    """
    Integration Test: Verifies the flow from Logic layer to InsightEngine.
    Ensures format switching (json vs markdown) works as expected.
    """
    await init_db()
    await init_thoughts_db()

    # Test JSON format
    json_report = await logic.get_value_report_core(format_type="json")
    assert isinstance(json_report, dict)
    assert "facts" in json_report
    assert "efficiency_indicators" in json_report

    # Test Markdown format
    md_report = await logic.get_value_report_core(format_type="markdown")
    assert isinstance(md_report, str)
    assert "# SharedMemory Fact Report" in md_report
