import aiosqlite
import pytest

from shared_memory.database import async_get_connection, init_db, update_access


@pytest.mark.asyncio
async def test_init_db_creates_tables(temp_db):
    await init_db()
    async with aiosqlite.connect(temp_db) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        table_names = [t[0] for t in tables]

    assert "entities" in table_names
    assert "knowledge_metadata" in table_names
    assert "audit_logs" in table_names
    assert "snapshots" in table_names


@pytest.mark.asyncio
async def test_update_access_and_stability(temp_db):
    await init_db()
    # Insert a mock entity first (FK constraint)
    async with await async_get_connection() as conn:
        await conn.execute(
            "INSERT INTO entities (name, entity_type) VALUES ('test_node', 'test')"
        )
        await conn.commit()

        # First access
        await update_access("test_node")

        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        )
        row = await cursor.fetchone()
        assert row[0] == 1
        initial_stability = row[1]

        # Second access (stability should increase)
        await update_access("test_node")
        cursor = await conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        )
        row = await cursor.fetchone()
        assert row[0] == 2
        assert row[1] > initial_stability


@pytest.mark.asyncio
async def test_migration_from_partial_schema(temp_db):
    """Verifies that init_db correctly migrates a database with a partial schema."""
    # 1. Setup a partial schema (simulating an older version)
    async with aiosqlite.connect(temp_db) as conn:
        await conn.execute(
            """
            CREATE TABLE entities (
                name TEXT PRIMARY KEY,
                entity_type TEXT,
                description TEXT
            )
        """
        )
        # Add only one of the migration columns to trigger the original bug
        await conn.execute(
            "ALTER TABLE entities ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        await conn.commit()

    # 2. Run init_db()
    await init_db()

    # 3. Verify all columns are now present
    async with aiosqlite.connect(temp_db) as conn:
        cursor = await conn.execute("PRAGMA table_info(entities)")
        columns = [col[1] for col in await cursor.fetchall()]

    expected_columns = [
        "name",
        "entity_type",
        "description",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "importance",
    ]
    for col in expected_columns:
        assert col in columns, f"Column {col} is missing from entities table"


@pytest.mark.asyncio
async def test_migration_relations_partial(temp_db):
    """Verifies that relations table is correctly migrated if columns are missing."""
    # Setup partial relations table
    async with aiosqlite.connect(temp_db) as conn:
        await conn.execute("CREATE TABLE entities (name TEXT PRIMARY KEY)")
        await conn.execute(
            """
            CREATE TABLE relations (
                source TEXT,
                target TEXT,
                relation_type TEXT,
                PRIMARY KEY (source, target, relation_type),
                FOREIGN KEY (source) REFERENCES entities (name),
                FOREIGN KEY (target) REFERENCES entities (name)
            )
        """
        )
        await conn.execute(
            "ALTER TABLE relations ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        await conn.commit()

    await init_db()

    async with aiosqlite.connect(temp_db) as conn:
        cursor = await conn.execute("PRAGMA table_info(relations)")
        columns = [col[1] for col in await cursor.fetchall()]

    assert "created_by" in columns
