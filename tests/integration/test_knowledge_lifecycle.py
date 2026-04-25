import pytest
import json
from shared_memory.logic import save_memory_core, read_memory_core, manage_knowledge_activation_core, list_inactive_knowledge_core

@pytest.mark.asyncio
async def test_knowledge_lifecycle_integration(mock_llm):
    """
    Tests the full lifecycle of knowledge.
    """
    agent = "lifecycle_agent"
    
    # 1. Create Knowledge
    mock_llm.models.set_response("generate_content", json.dumps({"conflict": False, "reason": "No conflict"}))
    
    await save_memory_core(
        entities=[{"name": "LifecycleNode", "description": "Testing lifecycle"}],
        observations=["Observation 1"],
        agent_id=agent
    )
    
    # 2. Search (Active)
    res = await read_memory_core("LifecycleNode")
    assert any(e["name"] == "LifecycleNode" for e in res["graph"]["entities"])
    
    # 3. Deactivate (Archive)
    await manage_knowledge_activation_core(["LifecycleNode"], "inactive")
    
    # 4. Search (Should be hidden from normal search)
    res_hidden = await read_memory_core("LifecycleNode")
    assert not any(e["name"] == "LifecycleNode" for e in res_hidden["graph"]["entities"])
    
    # 5. List Inactive
    res_inactive = await list_inactive_knowledge_core()
    assert any(item["name"] == "LifecycleNode" for item in res_inactive["entities"])
    
    # 6. Reactivate
    await manage_knowledge_activation_core(["LifecycleNode"], "active")
    
    # 7. Search (Visible again)
    res_final = await read_memory_core("LifecycleNode")
    assert any(e["name"] == "LifecycleNode" for e in res_final["graph"]["entities"])

@pytest.mark.asyncio
async def test_conflict_detection_integration(mock_llm):
    """Tests that save_memory handles AI-detected conflicts correctly."""
    agent = "conflict_agent"
    entity = "ConflictNode"
    
    # 1. First, create some existing context so check_conflict actually runs
    mock_llm.models.set_response("generate_content", json.dumps({"conflict": False}))
    await save_memory_core(
        entities=[{"name": entity, "description": "Node for conflict testing"}],
        observations=[{"entity_name": entity, "content": "Existing truth: The sky is blue."}],
        agent_id=agent
    )
    
    # 2. Now, steer mock to REPORT a conflict for the NEXT observation
    conflict_reason = "This information contradicts previous entry."
    mock_llm.models.set_response("generate_content", json.dumps({
        "conflict": True, 
        "reason": conflict_reason
    }))
    
    result = await save_memory_core(
        observations=[{"entity_name": entity, "content": "The sky is green."}],
        agent_id=agent
    )
    
    assert "CONFLICTS DETECTED" in result
    assert conflict_reason in result
