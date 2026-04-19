
import asyncio
import importlib.util
import os
import shutil
from datetime import datetime
from typing import List

import aiosqlite
from shared_memory.utils import get_db_path, get_logger

logger = get_logger("migration")

class MigrationManager:
    """
    Manages database schema migrations for SharedMemoryServer.
    Tracks applied versions in the 'schema_migrations' table.
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_db_path()
        # Path resolution now local to the package
        self.migrations_dir = os.path.join(os.path.dirname(__file__), "versions")
        os.makedirs(self.migrations_dir, exist_ok=True)

    async def _init_migration_table(self, conn: aiosqlite.Connection):
        """Ensures the schema_migrations tracking table exists."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()

    async def get_applied_versions(self, conn: aiosqlite.Connection) -> List[int]:
        """Returns a list of already applied migration versions."""
        cursor = await conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [row[0] for row in await cursor.fetchall()]

    def _get_migration_scripts(self) -> List[dict]:
        """Scans the versions directory and returns valid migration scripts."""
        scripts = []
        if not os.path.exists(self.migrations_dir):
            return []

        for filename in os.listdir(self.migrations_dir):
            if filename.startswith("v") and filename.endswith(".py"):
                try:
                    # Expecting format: v001_name.py
                    v_str = filename.split("_")[0][1:]
                    version = int(v_str)
                    scripts.append({
                        "version": version,
                        "path": os.path.join(self.migrations_dir, filename),
                        "name": filename
                    })
                except (ValueError, IndexError):
                    logger.warning(f"Skipping invalid migration filename: {filename}")
        
        return sorted(scripts, key=lambda x: x["version"])

    async def run_migrations(self, conn: aiosqlite.Connection):
        """
        Detects and applies pending migrations.
        Automatically performs a DB backup before the first pending migration.
        """
        await self._init_migration_table(conn)
        applied = await self.get_applied_versions(conn)
        pending = [s for s in self._get_migration_scripts() if s["version"] not in applied]

        if not pending:
            logger.debug("No pending migrations found.")
            return

        # --- Backup Phase ---
        backup_path = f"{self.db_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        logger.info(f"Backing up database to {backup_path} before migrations...")
        try:
            shutil.copy2(self.db_path, backup_path)
        except Exception as e:
            logger.error(f"Migration aborted: Backup failed: {e}")
            raise RuntimeError(f"Database backup failed: {e}")

        # --- Execution Phase ---
        for script in pending:
            version = script["version"]
            name = script["name"]
            logger.info(f"Applying migration v{version}: {name}")

            try:
                # Load module dynamically
                spec = importlib.util.spec_from_file_location(f"migration_v{version}", script["path"])
                module = importlib.util.module_from_spec(spec)
                if spec.loader:
                    spec.loader.exec_module(module)

                # Execute
                if hasattr(module, "migrate"):
                    await module.migrate(conn)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                        (version, name)
                    )
                    await conn.commit()
                    logger.info(f"Successfully applied v{version}")
                else:
                    raise AttributeError(f"Migration {name} missing 'migrate' function")

            except Exception as e:
                logger.error(f"CRITICAL: Failed to apply migration v{version} ({name}): {e}")
                raise

        logger.info("All pending migrations applied successfully.")

async def run_standalone():
    """CLI entry point for manual migration run."""
    from shared_memory.database import async_get_connection
    mgr = MigrationManager()
    async with await async_get_connection() as conn:
        await mgr.run_migrations(conn)

if __name__ == "__main__":
    asyncio.run(run_standalone())
