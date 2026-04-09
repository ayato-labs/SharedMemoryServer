import pytest

from shared_memory.database import async_get_connection, init_db, update_access
from shared_memory.graph import save_entities, save_observations, save_relations


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_save_entities(mock_gemini):
    async with await async_get_connection() as conn:
        entities = [
            {"name": "Alice", "entity_type": "person", "description": "A developer"},
            {"name": "Bob", "entity_type": "person", "description": "A designer"},
        ]
        res = await save_entities(entities, "test_agent", conn)
        await conn.commit()

        assert "Saved 2 entities" in res

        # Verify in DB
        cursor = await conn.execute(
            "SELECT name, entity_type FROM entities WHERE name = 'Alice'"
        )
        row = await cursor.fetchone()
        assert row[0] == "Alice"
        assert row[1] == "person"


@pytest.mark.asyncio
async def test_access_stability():
    async with await async_get_connection() as conn:
        # Insert a dummy knowledge metadata entry for testing
        await conn.execute(
            "INSERT INTO knowledge_metadata (content_id, access_count, stability) VALUES ('test_node', 0, 0.5)"
        )
        await conn.commit()

        # First access
        await update_access("test_node", conn)

        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        )
        row = await cursor.fetchone()
        assert row[0] == 1
        initial_stability = row[1]

        # Second access (stability should increase)
        await update_access("test_node", conn)
        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        )
        row = await cursor.fetchone()
        assert row[0] == 2
        assert row[1] > initial_stability


@pytest.mark.asyncio
async def test_save_relations():
    async with await async_get_connection() as conn:
        # Need entities first
        await conn.execute("INSERT INTO entities (name) VALUES ('Alice'), ('Bob')")

        relations = [{"source": "Alice", "target": "Bob", "relation_type": "colleague"}]
        res = await save_relations(relations, "test_agent", conn)
        await conn.commit()

        assert "Saved 1 relations" in res
        cursor = await conn.execute(
            "SELECT relation_type FROM relations WHERE source = 'Alice'"
        )
        row = await cursor.fetchone()
        assert row[0] == "colleague"


@pytest.mark.asyncio
async def test_save_observations(mock_gemini):
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name) VALUES ('Alice')")

        obs = [{"entity_name": "Alice", "content": "Likes Python"}]
        res, conflicts = await save_observations(obs, "test_agent", conn)
        await conn.commit()

        assert "Saved 1 observations" in res
        assert len(conflicts) == 0

        cursor = await conn.execute(
            "SELECT content FROM observations WHERE entity_name = 'Alice'"
        )
        row = await cursor.fetchone()
        assert row[0] == "Likes Python"


@pytest.mark.asyncio
async def test_conflict_detection(mock_gemini):
    # Setup: Mock Gemini to return a conflict
    mock_gemini.models.generate_content.return_value.text = (
        '{"conflict": true, "reason": "Contradicts previous info"}'
    )

    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name) VALUES ('Alice')")
        await conn.execute(
            "INSERT INTO observations (entity_name, content) VALUES ('Alice', 'Alice is in Tokyo')"
        )

        obs = [{"entity_name": "Alice", "content": "Alice is in London"}]
        res, conflicts = await save_observations(obs, "test_agent", conn)

        assert len(conflicts) == 1
        assert conflicts[0]["entity"] == "Alice"
        assert "Contradicts" in conflicts[0]["reason"]


@pytest.mark.asyncio
async def test_get_graph_data():
    await init_db()
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Alice', 'person')")
        await conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Bob', 'person')")
        await conn.execute(
            "INSERT INTO relations (source, target, relation_type) VALUES ('Alice', 'Bob', 'knows')"
        )
        await conn.execute(
            "INSERT INTO observations (entity_name, content) VALUES ('Alice', 'Works hard')"
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_save_entities_invalid_input(mock_gemini):
    async with await async_get_connection() as conn:
        # 1. Empty name
        res = await save_entities(
            [{"name": "", "description": "no name"}], "test_agent", conn
        )
        assert "Error" in res

        # 2. Out of range importance (should be clamped/defaulted)
        await save_entities([{"name": "ClampMe", "importance": 100}], "test_agent", conn)
        cursor = await conn.execute(
            "SELECT importance FROM entities WHERE name = 'ClampMe'"
        )
        row = await cursor.fetchone()
        assert row[0] == 10


@pytest.mark.asyncio
async def test_save_relations_invalid_input():
    async with await async_get_connection() as conn:
        # Missing fields
        res = await save_relations([{"source": "A"}], "test_agent", conn)
        assert "Errors: 1" in res


@pytest.mark.asyncio
async def test_save_observations_side_effects(mock_gemini):
    async with await async_get_connection() as conn:
        await conn.execute("INSERT INTO entities (name, importance) VALUES ('Alice', 5)")
        await conn.commit()

        # Saving an observation should increment importance
        await save_observations(
            [{"entity_name": "Alice", "content": "Update"}], "test_agent", conn
        )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT importance FROM entities WHERE name = 'Alice'"
        )
        row = await cursor.fetchone()
        assert row[0] == 6
