import asyncio
import pytest
from shared_memory.logic import save_memory_core, read_memory_core

@pytest.mark.asyncio
async def test_heavy_concurrency_writes(mock_llm):
    """
    Stress test: 20 concurrent save_memory calls.
    Verifies that the retry_on_db_lock decorator and aiosqlite transactions
    maintain integrity under pressure.
    """
    num_tasks = 20
    
    async def task(i):
        return await save_memory_core(
            entities=[{
                "name": f"ConcurrentNode_{i}", 
                "description": f"Stress test node {i}"
            }],
            agent_id=f"agent_{i}"
        )

    # Launch all tasks simultaneously
    results = await asyncio.gather(*[task(i) for i in range(num_tasks)], return_exceptions=True)
    
    # Analyze results
    success_count = 0
    errors = []
    for i, res in enumerate(results):
        if isinstance(res, str) and "Saved 1 entities" in res:
            success_count += 1
        else:
            errors.append(f"Task {i} failed: {res}")
            
    # Verify all succeeded
    assert success_count == num_tasks, f"Only {success_count}/{num_tasks} tasks succeeded. Errors: {errors}"
    
    # Verify all nodes actually exist in DB
    all_memory = await read_memory_core()
    entities_in_db = [e["name"] for e in all_memory["graph"]["entities"]]
    
    for i in range(num_tasks):
        assert f"ConcurrentNode_{i}" in entities_in_db

@pytest.mark.asyncio
async def test_sequential_vs_concurrent_consistency(mock_llm):
    """Verifies that concurrent updates to the same entity don't cause deadlocks or corrupt data."""
    entity_name = "HotEntity"
    
    # Ensure entity exists so observations are retrieved by name filter
    await save_memory_core(
        entities=[{"name": entity_name, "description": "High traffic node"}],
        agent_id="test_agent"
    )
    
    async def update_obs(i):
        return await save_memory_core(
            observations=[{"entity_name": entity_name, "content": f"Update {i}"}],
            agent_id="test_agent"
        )
        
    # 10 concurrent updates to the same entity
    await asyncio.gather(*[update_obs(i) for i in range(10)])
    
    res = await read_memory_core(entity_name)
    assert len(res["graph"]["observations"]) >= 10
