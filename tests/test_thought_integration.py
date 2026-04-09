import pytest

from shared_memory import database, server, thought_logic
from shared_memory.thought_logic import get_thought_history


@pytest.fixture(autouse=True)
async def init_test_dbs(mock_env):
    """Initializes both knowledge and thoughts databases for each test."""
    await database.init_db()
    await thought_logic.init_thoughts_db()


@pytest.mark.asyncio
async def test_sequential_thinking_tool_integration():
    """
    Tests the sequential_thinking tool integration within the FastMCP server.
    Ensures that the tool is registered and can be called.
    """
    # Simulate tool call via the mcp instance
    result = await server.sequential_thinking(
        thought="Thinking about adding a new entity",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="integration_session",
    )

    assert result["thoughtNumber"] == 1
    assert result["nextThoughtNeeded"] is True

    # Verify persistence
    history = await get_thought_history("integration_session")
    assert len(history) == 1
    assert history[0]["thought"] == "Thinking about adding a new entity"


@pytest.mark.asyncio
async def test_thought_and_memory_coexistence():
    """
    Tests that thought processing and memory saving can coexist without conflict.
    """
    # 1. Start thinking
    await server.sequential_thinking(
        thought="I will save an entity now",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="coexist_session",
    )

    # 2. Save memory
    await server.save_memory(
        entities=[
            {
                "name": "CoexistEntity",
                "entity_type": "Test",
                "description": "Testing coexistence",
            }
        ]
    )

    # 3. Finish thinking
    await server.sequential_thinking(
        thought="Entity saved successfully",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id="coexist_session",
    )

    # 4. Verify both exist
    history = await get_thought_history("coexist_session")
    assert len(history) == 2

    # Check graph memory
    graph_data = await server.get_graph_data(query="CoexistEntity")
    assert any(e["name"] == "CoexistEntity" for e in graph_data["entities"])
