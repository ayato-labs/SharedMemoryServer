import json

import pytest

from shared_memory.database import async_get_connection, init_db
from shared_memory.logic import (
    read_memory_core as perform_search,
)
from shared_memory.logic import (
    synthesize_entity as synthesize_knowledge,
)


@pytest.fixture(autouse=True)
async def setup_db(mock_gemini):
    await init_db()


@pytest.mark.asyncio
async def test_perform_search(mock_gemini):
    async with await async_get_connection() as conn:
        # Mock data
        await conn.execute(
            "INSERT INTO entities (name, description) "
            "VALUES ('Python', 'A programming language')"
        )
        await conn.execute(
            "INSERT INTO bank_files (filename, content) "
            "VALUES ('python_guide.md', 'Python is great')"
        )
        # Mock embedding and metadata
        vector_json = json.dumps([0.1] * 768).encode("utf-8")
        await conn.execute(
            "INSERT INTO embeddings (content_id, vector, model_name) "
            "VALUES ('Python', ?, 'models/text-embedding-004')",
            (vector_json,),
        )
        await conn.execute(
            "INSERT INTO knowledge_metadata (content_id, access_count) "
            "VALUES ('Python', 10)"
        )
        await conn.commit()

    # Run search
    res = await perform_search("Python")
    graph_data = res["graph"]

    assert any(e["name"] == "Python" for e in graph_data["entities"])


@pytest.mark.asyncio
async def test_synthesize_knowledge(mock_gemini):
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO entities (name, entity_type, description) "
            "VALUES ('Alice', 'person', 'Dev')"
        )
        await conn.execute(
            "INSERT INTO entities (name, entity_type, description) "
            "VALUES ('Project X', 'concept', 'A project')"
        )
        await conn.execute(
            "INSERT INTO observations (entity_name, content) "
            "VALUES ('Alice', 'Expert in Go')"
        )
        await conn.execute(
            "INSERT INTO relations (source, target, relation_type) "
            "VALUES ('Alice', 'Project X', 'leads')"
        )
        await conn.commit()

    # Mock generation
    mock_gemini.models.generate_content.return_value.text = (
        "Alice is a leading Go developer on Project X."
    )

    res = await synthesize_knowledge("Alice")
    assert "Alice" in res
    assert "Go" in res
