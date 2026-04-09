import asyncio
import json
import os
import sqlite3

from shared_memory import thought_logic, utils


async def test_knowledge_injection():
    print("Setting up test environment...")

    # 1. Use a temporary database for testing if needed,
    # but here we'll just ensure the tables are ready.
    # We use mocking or direct DB insertion to avoid Gemini dependency.

    db_path = utils.get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Injecting mock data directly into SQLite...")
    try:
        # Clear old test data
        cursor.execute("DELETE FROM entities WHERE name='SQLite'")
        cursor.execute("DELETE FROM observations WHERE entity_name='SQLite'")

        # Insert Entity
        cursor.execute(
            "INSERT INTO entities (name, entity_type, description, importance) "
            "VALUES (?, ?, ?, ?)",
            (
                "SQLite",
                "Database",
                "Relational storage engine used in this project.",
                8,
            ),
        )

        # Insert Observation
        cursor.execute(
            "INSERT INTO observations (entity_name, content, created_by) "
            "VALUES (?, ?, ?)",
            (
                "SQLite",
                "The SharedMemoryServer utilizes SQLite WAL mode for high concurrency.",
                "tester",
            ),
        )

        # Insert a Past Thought (in thoughts.db)
        thoughts_db_path = utils.get_thoughts_db_path()
        t_conn = sqlite3.connect(thoughts_db_path)
        t_cursor = t_conn.cursor()

        # Clear old thoughts
        t_cursor.execute(
            "DELETE FROM thought_history WHERE session_id='past_session_456'"
        )

        t_cursor.execute(
            """
            INSERT INTO thought_history (
                session_id, thought_number, total_thoughts,
                thought, next_thought_needed
            )
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                "past_session_456",
                1,
                1,
                "We should use SQLite for it's simplicity and local-first nature.",
                0,
            ),
        )

        t_conn.commit()
        t_conn.close()

        conn.commit()
        print("Mock data injected successfully.")
    except Exception as e:
        print(f"Setup failed: {e}")
        conn.close()
        return
    finally:
        conn.close()

    # 2. Trigger sequential thinking with a related keyword
    print("\nTesting sequential_thinking with 'SQLite'...")
    # This will call perform_keyword_search internally
    result = await thought_logic.process_thought_core(
        thought="I am thinking about how SQLite handles concurrent writes.",
        thought_number=1,
        total_thoughts=5,
        next_thought_needed=True,
        session_id="new_session_789",
    )

    # 3. Verify the result
    if "related_knowledge" in result and len(result["related_knowledge"]) > 0:
        print("\n--- TEST SUCCESS ---")
        print(f"Found {len(result['related_knowledge'])} related items:")
        for item in result["related_knowledge"]:
            print(f" - [{item['source']}] ID: {item['id']} (Score: {item['score']})")
    else:
        print("\n--- TEST FAILURE ---")
        print("No related_knowledge found in response.")
        print(f"Full Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_knowledge_injection())
