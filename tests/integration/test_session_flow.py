import json
from unittest.mock import AsyncMock, patch

import pytest

from shared_memory import logic, thought_logic
from shared_memory.database import async_get_connection


@pytest.mark.asyncio
async def test_sequential_thinking_to_distillation_flow(mock_llm):
    """
    INTEGRATION TEST: Verify the flow from Sequential Thinking to Knowledge Distillation.
    1. Run a session of 3 thoughts.
    2. Final thought should trigger auto_distill_knowledge.
    3. Verify knowledge is stored in the graph.
    """
    session_id = "test_session_123"
    
    # Setup mock LLM response for distillation
    distilled_json = {
        "entities": [{
            "name": "Quantum Computing",
            "entity_type": "Field",
            "description": "Physics field"
        }],
        "relations": [],
        "observations": [{"entity_name": "Quantum Computing", "content": "Uses qubits."}]
    }
    mock_llm.models.set_response("generate_content", json.dumps(distilled_json))
    
    # 1. First thought
    await thought_logic.process_thought_core(
        session_id=session_id,
        thought="I am starting to research Quantum Computing.",
        thought_number=1,
        total_thoughts=3,
        next_thought_needed=True
    )
    
    # 2. Second thought
    await thought_logic.process_thought_core(
        session_id=session_id,
        thought="Qubits are the fundamental units of quantum information.",
        thought_number=2,
        total_thoughts=3,
        next_thought_needed=True
    )
    
    # 3. Final thought (should trigger distillation)
    # We patch auto_distill_knowledge to ensure it's called, but we also want to see the effect.
    # Actually, let's let it run but we might need to wait for the background task.
    # auto_distill_knowledge is awaited in save_thought_logic when next_thought_needed=False.
    
    await thought_logic.process_thought_core(
        session_id=session_id,
        thought="In conclusion, Quantum Computing is revolutionary.",
        thought_number=3,
        total_thoughts=3,
        next_thought_needed=False
    )
    
    # 4. Verify graph contains the distilled knowledge
    # We need to ensure background tasks (like incremental distillation) are finished
    from shared_memory.tasks import wait_for_background_tasks
    await wait_for_background_tasks()
    
    # We need to use read_memory_core or direct DB check
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM entities WHERE name='Quantum Computing'")
        row = await cursor.fetchone()
        assert row is not None
        
        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name='Quantum Computing'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert "qubits" in row[0].lower()

@pytest.mark.asyncio
async def test_read_memory_hybrid_search(mock_llm):
    """
    INTEGRATION TEST: Verify that read_memory combines keyword and semantic search.
    """
    # 1. Save some data
    await logic.save_memory_core(
        entities=[
            {"name": "Python", "description": "Programming language"},
            {"name": "Java", "description": "A coffee inspired language"}
        ]
    )
    
    # 2. Mock semantic search (batch_cosine_similarity) to return high score for Java
    # and perform_search to include it
    def side_effect(cids, conn=None):
        res = {"entities": [], "relations": [], "observations": []}
        if "Java" in cids:
            res["entities"].append({"name": "Java", "description": "Other language"})
        if "Python" in cids:
            res["entities"].append({"name": "Python", "description": "Programming language"})
        return res

    with patch("shared_memory.search.get_graph_data_by_cids", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = side_effect
        # We need to make sure 'Java' is in top_cids. 
        # For simplicity, we just mock the return of get_graph_data_by_cids.
        result = await logic.read_memory_core(query="programming")
        
        # Verify both Python (keyword/direct) and Java (semantic result from mock) are present
        entity_names = [e["name"] for e in result["graph"]["entities"]]
        assert "Python" in entity_names
        assert "Java" in entity_names
