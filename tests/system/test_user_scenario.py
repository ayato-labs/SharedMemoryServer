import pytest

from shared_memory.logic import save_memory_core
from shared_memory.search import perform_search


@pytest.mark.asyncio
async def test_complete_expert_user_flow(fake_llm):
    """
    SYSTEM TEST: Comprehensive end-to-end flow.
    1. Automatic Bootstrap (Database + Migrations)
    2. Knowledge Injection (Entities, Relations, Bank Files)
    3. Retrieval (Semantic Hybrid Search)
    4. Lifecycle (Archival)
    5. Maintenance (Snapshot)
    """

    # --- 1. Injection Phase ---
    entities = [
        {
            "name": "Project Rigour",
            "entity_type": "security",
            "description": "Deterministic safety layer",
        }
    ]
    relations = [{"subject": "Project Rigour", "object": "LogicHive", "predicate": "secures"}]
    bank_files = [
        {
            "filename": "rigour_specs.md",
            "content": "# Rigour Specifications\nMust be deterministic.",
        }
    ]

    inject_res = await save_memory_core(
        entities=entities, relations=relations, bank_files=bank_files, agent_id="system_test_agent"
    )
    assert "Saved 1 entities" in inject_res
    assert "Saved 1 relations" in inject_res
    assert "Updated 1 bank files" in inject_res

    # --- 2. Retrieval Phase ---
    # Perform a hybrid search for 'security'
    # FakeGeminiClient will return text-dependent embeddings
    graph_data, bank_data = await perform_search("security")

    # Verify that 'Project Rigour' is found
    entity_names = [e["name"] for e in graph_data["entities"]]
    assert "Project Rigour" in entity_names
    # Verify relations found
    assert len(graph_data["relations"]) >= 1
    assert graph_data["relations"][0]["subject"] == "Project Rigour"

    # --- 3. Lifecycle Phase (Activation) ---
    from shared_memory.lifecycle import manage_knowledge_activation_logic

    # Deactivate 'Project Rigour'
    await manage_knowledge_activation_logic(["Project Rigour"], "inactive")

    # Verify it is no longer found in standard search (perform_search filters for 'active')
    graph_data_after, _ = await perform_search("security")
    entity_names_after = [e["name"] for e in graph_data_after["entities"]]
    assert "Project Rigour" not in entity_names_after

    # --- 4. Maintenance (Snapshot) ---
    from shared_memory.management import create_snapshot_logic, list_snapshots_logic

    snapshot_msg = await create_snapshot_logic("post_test_cleanup", "Final state of system test")
    assert "Snapshot 'post_test_cleanup' created" in snapshot_msg

    snapshots = await list_snapshots_logic()
    assert any(s["name"] == "post_test_cleanup" for s in snapshots)

    print(
        "System test complete: Verified bootstrap, injection, search, lifecycle, and snapshotting."
    )
