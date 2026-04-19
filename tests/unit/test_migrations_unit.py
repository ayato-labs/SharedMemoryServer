
import pytest
import aiosqlite
import os
from shared_memory.database import init_db, async_get_connection
from shared_memory.graph import save_relations
from shared_memory.bank import save_bank_files

@pytest.mark.asyncio
async def test_migration_v1_auto_applied_unit(mock_env):
    """
    Unit test: Verify that migration v1 is automatically applied upon init_db
    and that relations can now be saved without strict foreign key constraints.
    """
    # init_db is called inside async_get_connection
    async with await async_get_connection() as conn:
        # 1. Check if migration was recorded
        cursor = await conn.execute("SELECT version FROM schema_migrations WHERE version = 1")
        row = await cursor.fetchone()
        assert row is not None, "Migration v1 should be recorded in schema_migrations"

        # 2. Verify we can save a relation where subject/object don't exist in entities
        # (This previously failed with FOREIGN KEY constraint failed)
        relations = [
            {
                "subject": "NonExistentSubject",
                "object": "NonExistentObject",
                "predicate": "links_to"
            }
        ]
        # This call should succeed now
        res = await save_relations(relations, "test_agent", conn)
        assert "Saved 1 relations" in res

@pytest.mark.asyncio
async def test_bank_files_mentions_robustness_after_migration_unit(mock_env):
    """
    Unit test: Verify that bank files can mention entities without FK errors.
    """
    # Ensure there is at least one entity to mention
    async with await async_get_connection() as conn:
        await conn.execute("INSERT OR REPLACE INTO entities (name) VALUES (?)", ("TargetEntity",))
        await conn.commit()

        bank_files = {
            "test_mentions.md": "This file mentions TargetEntity."
        }
        
        # This call used to fail due to relations FK constraint
        # Now it should succeed
        res = await save_bank_files(bank_files, "test_agent", conn)
        assert "Updated 1 bank files" in res

        # Verify the relation was actually created
        cursor = await conn.execute(
            "SELECT * FROM relations WHERE subject = ? AND object = ?",
            ("test_mentions.md", "TargetEntity")
        )
        row = await cursor.fetchone()
        assert row is not None, "Relation from bank file to entity should be created"
