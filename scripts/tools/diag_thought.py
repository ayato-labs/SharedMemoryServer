import asyncio
import os

from shared_memory import thought_logic


async def diag():
    print(f"CWD: {os.getcwd()}")
    print(f"Thoughts DB Path: {thought_logic.get_thoughts_db_path()}")

    # Try to process a thought
    try:
        result = await thought_logic.process_thought_core(
            thought="Diagnostic thought from script",
            thought_number=1,
            total_thoughts=1,
            next_thought_needed=False,
            session_id="diag_session"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(diag())
