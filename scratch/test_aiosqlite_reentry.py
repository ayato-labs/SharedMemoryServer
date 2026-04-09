import asyncio
import aiosqlite
import threading

async def test():
    conn = await aiosqlite.connect("test.db")
    # Check if thread is started
    print(f"Started attribute: {conn._started}")
    # Find aiosqlite threads
    count = sum(1 for t in threading.enumerate() if "sqlite" in t.name.lower())
    print(f"SQLite threads count: {count}")
    
    try:
        async with conn:
            print("Entered context manager")
    except RuntimeError as e:
        print(f"Caught RuntimeError in context manager: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test())
