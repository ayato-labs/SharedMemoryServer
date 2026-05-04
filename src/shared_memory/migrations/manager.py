import os

import aiosqlite

from shared_memory.common.utils import get_logger

logger = get_logger(\"migrations\")


class MigrationManager:
    \"\"\"
    Handles database schema evolution.
    SSoT Principle: Schema should match the code definition.
    \"\"\"

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def run_migrations(self, conn: aiosqlite.Connection):
        \"\"\"Applies all pending migrations within the provided connection.\"\"\"
        logger.info(\"Checking for pending migrations...\")
        # For now, we ensure the metadata table exists for SSoT tracking
        await conn.execute(
            \"\"\"
            CREATE TABLE IF NOT EXISTS knowledge_metadata (
                content_id TEXT PRIMARY KEY,
                access_count INTEGER DEFAULT 0,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                importance_score REAL DEFAULT 1.0,
                stability REAL DEFAULT 1.0,
                decay_rate REAL DEFAULT 0.01,
                is_active BOOLEAN DEFAULT 1
            )
            \"\"\"
        )

        # Migration 1: Add is_active if missing
        from shared_memory.infra.database import _add_column_if_missing

        cursor = await conn.cursor()
        await _add_column_if_missing(cursor, \"knowledge_metadata\", \"is_active BOOLEAN DEFAULT 1\")

        # Migration 2: Embedding cache
        await conn.execute(
            \"\"\"
            CREATE TABLE IF NOT EXISTS embedding_cache (
                text TEXT PRIMARY KEY,
                embedding TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            \"\"\"
        )

        await conn.commit()
        logger.info(\"Migrations complete.\")
