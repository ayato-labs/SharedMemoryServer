import asyncio

import aiosqlite


class ConfiguredConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    async def __aenter__(self):
        print("Entering __aenter__")
        # Ensure ONLY ONE connect happens
        self.conn = await aiosqlite.connect(self.db_path)
        print("Thread started")
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("Entering __aexit__")
        await self.conn.close()

async def async_get_connection():
    return ConfiguredConnection("test.db")

async def test():
    # This matches the pattern in our codebase
    async with await async_get_connection() as conn:
        print("Inside context manager")
        await conn.execute("SELECT 1")

if __name__ == "__main__":
    asyncio.run(test())
