from unittest.mock import AsyncMock

import pytest

from shared_memory.core.search import perform_search

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_hybrid_search_with_tags_and_heat(monkeypatch, db_conn):
    """
    Integration test: Verify Hybrid Search (Semantic + Tag + Heat).
    - 'python' (semantic)
    - '#mcp' (tag)
    - Heat boost for frequently accessed items
    """
    # 1. Setup Data
    # Item A: High semantic match, low access
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        ("ItemA", "test", "Deep python logic", "active")
    )
    # Item B: Low semantic match, but HAS TAG match
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        ("ItemB", "test", "Something else", "active")
    )
    await db_conn.execute(
        "INSERT INTO tags (tag, content_id, content_type) VALUES (?, ?, ?)",
        ("#mcp", "ItemB", "entity")
    )
    # Item C: Low semantic, but HIGH HEAT
    await db_conn.execute(
        "INSERT INTO entities (name, entity_type, description, status) VALUES (?, ?, ?, ?)",
        ("ItemC", "test", "Common utils", "active")
    )
    await db_conn.execute(
        "INSERT INTO knowledge_metadata (content_id, access_count, last_accessed) VALUES (?, ?, ?)",
        ("ItemC", 1000, "2026-05-01T00:00:00Z")
    )
    
    # Mock Embeddings
    mock_compute = AsyncMock(side_effect=lambda q: [0.9 if "python" in q else 0.1] * 768)
    monkeypatch.setattr("shared_memory.core.search.compute_embedding", mock_compute)
    
    # Mock DB for embeddings
    await db_conn.execute(
        "INSERT INTO embeddings (content_id, vector) VALUES (?, ?)",
        ("ItemA", str([0.9] * 768))
    )
    await db_conn.execute(
        "INSERT INTO embeddings (content_id, vector) VALUES (?, ?)",
        ("ItemB", str([0.1] * 768))
    )
    await db_conn.execute(
        "INSERT INTO embeddings (content_id, vector) VALUES (?, ?)",
        ("ItemC", str([0.1] * 768))
    )
    await db_conn.commit()

    # 2. Perform Search
    # Query: "python #mcp"
    graph_data, _ = await perform_search("python mcp")
    
    results = [e["name"] for e in graph_data["entities"]]
    
    # ItemA should be top (Semantic), ItemB should be near (Tag), ItemC should be boosted (Heat)
    assert "ItemA" in results
    assert "ItemB" in results
    assert "ItemC" in results
    
    # Verify access count update
    cursor = await db_conn.execute(
        "SELECT access_count FROM knowledge_metadata WHERE content_id = 'ItemA'"
    )
    assert (await cursor.fetchone())[0] == 1
