import aiosqlite


class BaseSQLiteRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn
