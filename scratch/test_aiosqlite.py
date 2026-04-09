import asyncio
import aiosqlite
import os

async def test():
    try:
        # This is what database.py does
        conn = await aiosqlite.connect("test.db")
        print("Awaited successfully")
    except TypeError as e:
        print(f"Caught expected TypeError: {e}")
    except Exception as e:
        print(f"Caught unexpected Exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test())
