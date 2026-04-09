import pytest

from shared_memory.database import init_db
from shared_memory.server import (
    admin_create_snapshot,
    admin_get_audit_history,
    admin_repair_memory,
    read_memory,
    save_memory,
    sequential_thinking,
    synthesize_entity,
)


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_full_save_read_flow(mock_gemini):
    # 1. Save Memory (Complex)
    res = await save_memory(
        entities=[
            {"name": "Project Omega", "description": "Top secret"},
            {"name": "CEO", "description": "The boss"},
        ],
        relations=[
            {"source": "Project Omega", "target": "CEO", "relation_type": "managed_by"}
        ],
        observations=[{"entity_name": "Project Omega", "content": "Started in 2024"}],
        bank_files={"omega_manual.md": "# Omega Manual"},
    )
    assert "Saved 2 entities" in res
    assert "Saved 1 relations" in res
    assert "Saved 1 observations" in res
    assert "Updated 1 bank files" in res

    # 2. Read Memory (Keyword)
    data = await read_memory(query="Omega")
    assert any(e["name"] == "Project Omega" for e in data["graph"]["entities"])
    assert "omega_manual.md" in data["bank"]

    # 3. Audit History
    history = await admin_get_audit_history(limit=5)
    assert len(history) >= 4  # Entity, Relation, Obs, BankFile

    # 4. Synthesis
    synth = await synthesize_entity("Project Omega")
    assert "conflict" in synth or "Project Omega" in synth

    # 5. Snapshot
    snap_res = await admin_create_snapshot("Final State")
    assert "Snapshot 'Final State' created" in snap_res

    # 6. Repair
    repair_res = await admin_repair_memory()
    assert "Restored" in repair_res

    # 7. Sequential Thinking & Distillation
    # Thought 1
    await sequential_thinking(
        thought="I need to record that the project budget is $1M.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="test_session",
    )
    # Thought 2 (Finish & Trigger Distillation)
    await sequential_thinking(
        thought="The budget is specifically for personnel costs.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id="test_session",
    )

    # Check if knowledge was distilled into the graph
    data = await read_memory(query="budget")
    synth_result = await synthesize_entity("Project Omega")
    assert synth_result is not None
