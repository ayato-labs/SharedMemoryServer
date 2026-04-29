import json

import pytest

from shared_memory import logic, thought_logic


@pytest.mark.asyncio
@pytest.mark.system
async def test_reasoning_synergy_and_distillation(mock_llm):
    """
    Simulates a complex multi-session scenario:
    1. Session A: Reasoning generates knowledge via Incremental Distillation.
    2. Session B: New session salvages knowledge from Session A.
    3. Session A closure: Triggers final auto-distillation report.
    """
    session_a = "session_antigravity_arch"
    session_b = "session_dependency_check"

    # --- STEP 1: Session A (Knowledge Ingestion) ---
    # We mock the incremental distiller to return a specific entity.
    distill_result = {
        "entities": [
            {
                "name": "CoreEngine",
                "entity_type": "component",
                "description": "The main orchestrator.",
            }
        ],
        "relations": [],
        "observations": [{"entity_name": "CoreEngine", "content": "Uses WAL mode for SQLite."}],
    }
    mock_llm.models.set_response("generate_content", json.dumps(distill_result))

    # Process a thought in Session A
    # incremental_distill_knowledge is called as a background task in process_thought_core.
    # To ensure it finishes in test, we might need to wait or mock it to be sync,
    # but here we'll call process_thought_core and then briefly wait.
    await thought_logic.process_thought_core(
        thought="The CoreEngine is the heart of the system and it uses WAL mode.",
        thought_number=1,
        total_thoughts=5,
        next_thought_needed=True,
        session_id=session_a,
    )

    # Wait for background incremental distillation task
    from shared_memory.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    # Verify Session A knowledge was saved to Graph
    search_a = await logic.read_memory_core("CoreEngine")
    assert any(e["name"] == "CoreEngine" for e in search_a["graph"]["entities"]), (
        "CoreEngine should be distilled from Session A"
    )
    assert any("WAL mode" in o["content"] for o in search_a["graph"]["observations"]), (
        "Observation should be distilled"
    )

    # --- STEP 2: Session B (Knowledge Retrieval & Salvage) ---
    # Now simulate a DIFFERENT session asking about it.
    # We mock the salvage reranker if needed, but salvage_related_knowledge
    # uses semantic search which our mock_llm handles via embed_content.

    # Thought in Session B that should trigger salvage
    res_b = await thought_logic.process_thought_core(
        thought="I need to check how the CoreEngine handles database concurrency.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_b,
    )

    # Verify related_knowledge contains Session A's findings
    rel_k = res_b.get("related_knowledge", [])
    assert any("CoreEngine" in str(k) or "WAL mode" in str(k) for k in rel_k), (
        "Session B should salvage knowledge from Session A"
    )

    # --- STEP 3: Final Distillation on Closure ---
    # Mock the final distillation report
    final_report = {
        "entities": [
            {
                "name": "SharedMemoryServer",
                "entity_type": "system",
                "description": "A robust MCP server.",
            }
        ],
        "relations": [
            {
                "source": "CoreEngine",
                "target": "SharedMemoryServer",
                "relation_type": "part_of",
                "justification": "Primary component",
            }
        ],
        "observations": [],
    }
    mock_llm.models.set_response("generate_content", json.dumps(final_report))

    # Close Session A
    await thought_logic.process_thought_core(
        thought="Closing session after final review.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,  # Trigger wrap-up
        session_id=session_a,
    )

    # Wait for background final distillation
    from shared_memory.tasks import wait_for_background_tasks

    await wait_for_background_tasks()

    # Verify final synthesized knowledge exists
    search_final = await logic.read_memory_core("SharedMemoryServer")
    assert any(e["name"] == "SharedMemoryServer" for e in search_final["graph"]["entities"]), (
        "Final distillation should save the system entity"
    )

    # Check relation was saved
    # Note: relations are returned as a list of dicts in read_memory_core
    found_rel = False
    for r in search_final["graph"]["relations"]:
        if r["subject"] == "CoreEngine" and r["object"] == "SharedMemoryServer":
            found_rel = True
            break
    assert found_rel, "Relation from final distillation should be saved"
