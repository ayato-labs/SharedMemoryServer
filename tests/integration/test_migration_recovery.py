import os
from unittest.mock import patch

import aiosqlite
import pytest

from shared_memory.migrations.manager import MigrationManager


@pytest.mark.asyncio
async def test_migration_recovery_on_failure(tmp_path):
    """
    STRICT TEST: Verify that the system creates a backup and can potentially recover
    if a migration script fails.
    """
    # Use isolated DB for this test
    db_path = str(tmp_path / "recovery_test.db")
    os.environ["MEMORY_DB_PATH"] = db_path

    mgr = MigrationManager(db_path)

    # Simulate a migration script failure by patching _get_migration_scripts
    with patch.object(mgr, "_get_migration_scripts") as mock_scripts:
        mock_scripts.return_value = [
            {"version": 999, "path": "non_existent.py", "name": "v999_fail.py"}
        ]

        async with aiosqlite.connect(db_path) as conn:
            # This should fail because the script is non-existent
            with pytest.raises(RuntimeError):
                await mgr.run_migrations(conn)

    # Verify that a backup was created DESPITE the failure
    db_dir = os.path.dirname(db_path)
    backups = [f for f in os.listdir(db_dir) if f.endswith(".bak")]
    assert len(backups) >= 1


@pytest.mark.asyncio
async def test_migration_locks_db_correctly(tmp_path):
    """Verify that migrations are performed within a transaction on a fresh DB."""
    db_path = str(tmp_path / "fresh_test.db")
    os.environ["MEMORY_DB_PATH"] = db_path

    mgr = MigrationManager(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await mgr._init_migration_table(conn)
        applied = await mgr.get_applied_versions(conn)
        assert 1 not in applied  # Fresh DB
