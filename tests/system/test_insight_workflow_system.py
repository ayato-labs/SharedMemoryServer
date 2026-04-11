import pytest

from shared_memory.logic import (
    get_value_report_core,
    read_memory_core,
    save_memory_core,
)


@pytest.mark.asyncio
async def test_complete_knowledge_lifecycle_system():
    """
    System Test: Verifies the entire lifecycle of knowledge and
    its value quantification.
    Scenario:
    1. Agent stores domain-specific patterns.
    2. Agent queries the patterns multiple times during a task.
    3. Management retrieves the Insight Report to prove project
       understanding and efficiency.
    """
    # 1. Store complex knowledge (2 entities, 1 relation, 1 bank file)
    entities = [
        {
            "name": "AuthModule",
            "entity_type": "component",
            "description": "Handles OIDC flows"
        },
        {
            "name": "Database",
            "entity_type": "infrastructure",
            "description": "Managed PostgreSQL"
        }
    ]
    relations = [
        {"subject": "AuthModule", "object": "Database", "predicate": "writes_to"}
    ]
    bank_files = {
        "security_policy.md": "# Security\nAll connections must use TLS."
    }

    save_result = await save_memory_core(
        entities=entities,
        relations=relations,
        bank_files=bank_files,
        agent_id="test_system_agent"
    )
    assert "Saved 2 entities" in save_result
    assert "Saved 1 relations" in save_result

    # 2. Simulate workflow (3 hits, 1 miss)
    await read_memory_core(query="AuthModule") # Hit 1
    await read_memory_core(query="TLS")        # Hit 2 (Bank)
    await read_memory_core(query="Database")   # Hit 3
    await read_memory_core(query="ImaginaryFeature") # Miss 1

    # 3. Request Value Report (Simulate Admin Tool Call)
    # 3.1 JSON Format (for Dashboards)
    metrics = await get_value_report_core(format_type="json")

    # 3.2 Markdown Format (for Human Report)
    report = await get_value_report_core(format_type="markdown")

    # 4. Final System Validations
    f = metrics["facts"]
    assert f["stored_entities"] == 2
    assert f["stored_bank_files"] == 1
    assert f["total_search_queries"] == 4
    assert f["search_hit_rate_percent"] == 75.0 # 3/4

    # Verify report narrative
    assert "検索ヒット率 (Hit Rate): 75.0%" in report
    assert "活用係数 (Reuse Multiplier)" in report
    assert "観測事実" in report
