from typing import Any

import aiosqlite

from ripen.infra.database import AsyncSQLiteConnection, get_write_semaphore, init_db
from ripen.infra.repository import (
    AuditRepository,
    BankRepository,
    ConflictRepository,
    EmbeddingRepository,
    EntityRepository,
    GraphRepository,
    ManagementRepository,
    MetadataRepository,
    ObservationRepository,
    RelationRepository,
    SearchRepository,
    TagRepository,
    ThoughtRepository,
    TroubleshootingRepository,
)


class UnitOfWork:
    """
    Manages database transactions and ensures repository instances
    share the same connection within a session.
    """

    def __init__(self, is_thoughts: bool = False):
        self.is_thoughts = is_thoughts
        self._conn: aiosqlite.Connection | None = None
        self._semaphore = get_write_semaphore()
        self._management: ManagementRepository | None = None

    async def __aenter__(self):
        if self.is_thoughts:
            from ripen.common.utils import get_thoughts_db_path
            from ripen.core.thought_logic import init_thoughts_db

            await init_thoughts_db()
            self._conn = await AsyncSQLiteConnection(
                get_thoughts_db_path(), is_thoughts=True
            ).__aenter__()
        else:
            from ripen.common.utils import get_db_path

            await init_db()
            self._conn = await AsyncSQLiteConnection(get_db_path()).__aenter__()

        # Initialize repositories with this connection
        self.bank = BankRepository(self._conn)
        self.audit = AuditRepository(self._conn)
        self.entities = EntityRepository(self._conn)
        self.relations = RelationRepository(self._conn)
        self.observations = ObservationRepository(self._conn)
        self.conflicts = ConflictRepository(self._conn)
        self.embeddings = EmbeddingRepository(self._conn)
        self.troubleshooting = TroubleshootingRepository(self._conn)
        self.tags = TagRepository(self._conn)
        self.graph = GraphRepository(self._conn)
        self.search = SearchRepository(self._conn)
        self.thoughts = ThoughtRepository(self._conn)
        self.metadata = MetadataRepository(self._conn)
        self._management = ManagementRepository(self._conn)

        return self

    @property
    def management(self) -> ManagementRepository:
        return self._management

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        # The connection itself is a singleton managed by database.py
        # and doesn't need to be closed here, but we should clear our reference.
        self._conn = None

    async def commit(self):
        if self._conn:
            await self._conn.commit()

    async def rollback(self):
        if self._conn:
            await self._conn.rollback()

    async def execute(self, sql: str, params: Any = None):
        return await self._conn.execute(sql, params)


class SecureWriteContext:
    """
    Context manager that combines the write semaphore and a UnitOfWork.
    """

    def __init__(self, is_thoughts: bool = False):
        self.is_thoughts = is_thoughts
        self.uow = UnitOfWork(is_thoughts)
        self._semaphore = get_write_semaphore()

    async def __aenter__(self):
        await self._semaphore.acquire()
        return await self.uow.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.uow.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            self._semaphore.release()
