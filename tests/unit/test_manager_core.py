import os

import aiosqlite
import pytest

from shared_memory.migrations.manager import MigrationManager
from shared_memory.utils import get_db_path


@pytest.mark.asyncio
async def test_migration_manager_init():
    """Test MigrationManager initialization and path resolution."""
    mgr = MigrationManager()
    assert mgr.db_path == get_db_path()
    # The migrations_dir should be inside the package now
    assert "shared_memory" in mgr.migrations_dir
    assert "migrations" in mgr.migrations_dir
    assert os.path.exists(mgr.migrations_dir)


@pytest.mark.asyncio
async def test_migration_table_initialization():
    """Test that the tracking table is created correctly."""
    mgr = MigrationManager()
    async with aiosqlite.connect(mgr.db_path) as conn:
        await mgr._init_migration_table(conn)

        # Verify table exists
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_get_migration_scripts():
    """Test scanning for migration scripts."""
    mgr = MigrationManager()
    scripts = mgr._get_migration_scripts()

    # We should have at least v001
    assert len(scripts) >= 1
    versions = [s["version"] for s in scripts]
    assert 1 in versions
    assert scripts[0]["path"].endswith(".py")


@pytest.mark.asyncio
async def test_run_migrations_idempotency():
    """Test that running migrations twice doesn't cause errors."""
    mgr = MigrationManager()
    async with aiosqlite.connect(mgr.db_path) as conn:
        # First run
        await mgr.run_migrations(conn)
        applied = await mgr.get_applied_versions(conn)
        assert 1 in applied

        # Second run - should skip v001
        await mgr.run_migrations(conn)
        applied_again = await mgr.get_applied_versions(conn)
        assert applied == applied_again


@pytest.mark.asyncio
async def test_backup_creation_on_migration():
    """Test that a backup file is created before applying migrations."""
    mgr = MigrationManager()
    db_path = mgr.db_path

    # Ensure no migrations are applied yet by using a fresh DB (handled by fixture already)
    # But MigrationManager checks the DB directly.

    async with aiosqlite.connect(db_path) as conn:
        # Run migrations
        await mgr.run_migrations(conn)

    # Check for .bak files in the directory
    db_dir = os.path.dirname(db_path)
    backups = [f for f in os.listdir(db_dir) if f.endswith(".bak")]
    assert len(backups) >= 1
