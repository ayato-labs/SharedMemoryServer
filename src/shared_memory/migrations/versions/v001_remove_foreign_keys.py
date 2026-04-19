import aiosqlite

from shared_memory.utils import get_logger

logger = get_logger("migration_v001")


async def migrate(conn: aiosqlite.Connection):
    """
    Migration v001: Remove FOREIGN KEY constraints from relations and observations.
    This allows flexible linking between entities and other knowledge types (like bank files).
    """
    logger.info("Starting Migration v001...")

    # 1. Disable Foreign Keys during the shuffle
    await conn.execute("PRAGMA foreign_keys = OFF")

    try:
        # --- RELATIONS TABLE RECONSTRUCTION ---
        logger.info("Reconstructing 'relations' table...")

        # Create new table without FKs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS relations_new (
                subject TEXT,
                object TEXT,
                predicate TEXT,
                justification TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                status TEXT DEFAULT 'active',
                PRIMARY KEY (subject, object, predicate)
            )
        """)

        # Copy data
        await conn.execute("INSERT OR IGNORE INTO relations_new SELECT * FROM relations")

        # Drop old, rename new
        await conn.execute("DROP TABLE IF EXISTS relations")
        await conn.execute("ALTER TABLE relations_new RENAME TO relations")

        # --- OBSERVATIONS TABLE RECONSTRUCTION ---
        logger.info("Reconstructing 'observations' table...")

        # Create new table without FKs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS observations_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                status TEXT DEFAULT 'active'
            )
        """)

        # Copy data (respecting the sequence)
        await conn.execute(
            "INSERT OR IGNORE INTO observations_new (id, entity_name, content, timestamp, created_by, status) "
            "SELECT id, entity_name, content, timestamp, created_by, status FROM observations"
        )

        # Drop old, rename new
        await conn.execute("DROP TABLE IF EXISTS observations")
        await conn.execute("ALTER TABLE observations_new RENAME TO observations")

        logger.info("Migration v001 completed successfully.")

    except Exception as e:
        logger.error(f"Migration v001 failed: {e}")
        raise
    finally:
        await conn.execute("PRAGMA foreign_keys = ON")
