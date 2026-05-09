import pytest

from ripen.core import graph


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_entities_low_level(db_conn):
    """
    Unit Test: graph.save_entities の単体検証。
    """
    entities = [{"name": "LowLevelNode", "entity_type": "unit", "description": "Graph test"}]
    # No precomputed vectors provided -> should call compute_embeddings_bulk internally
    # Wait, graph.save_entities expects a connection
    msg = await graph.save_entities(entities, "graph_unit_tester", db_conn)
    assert "Saved 1 entities" in msg

    # 検証
    cursor = await db_conn.execute("SELECT * FROM entities WHERE name='LowLevelNode'")
    row = await cursor.fetchone()
    assert row["entity_type"] == "unit"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_relations_low_level(db_conn):
    """
    Unit Test: graph.save_relations の単体検証。
    """
    relations = [{"subject": "Alpha", "predicate": "leads_to", "object": "Beta"}]
    msg = await graph.save_relations(relations, "graph_unit_tester", db_conn)
    assert "Saved 1 relations" in msg

    # 検証
    cursor = await db_conn.execute("SELECT * FROM relations WHERE subject='Alpha'")
    row = await cursor.fetchone()
    assert row["predicate"] == "leads_to"
    assert row["object"] == "Beta"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_observations_low_level(db_conn, fake_llm):
    """
    Unit Test: graph.save_observations の単体検証。
    """
    # Observations require an existing entity or it will just create it.
    await db_conn.execute("INSERT INTO entities (name) VALUES ('ObsNode')")

    observations = [{"entity_name": "ObsNode", "content": "Graph observation"}]
    # save_observations returns (msg, conflicts)
    msg, conflicts = await graph.save_observations(observations, "graph_unit_tester", db_conn)

    assert "Saved 1 observations" in msg
    assert len(conflicts) == 0

    # 検証
    cursor = await db_conn.execute("SELECT * FROM observations WHERE entity_name='ObsNode'")
    row = await cursor.fetchone()
    assert row["content"] == "Graph observation"
