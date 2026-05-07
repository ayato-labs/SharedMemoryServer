import pytest

from shared_memory.core import thought_logic


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_thought_core_db_verification(db_conn, fake_llm):
    """
    Unit Test: process_thought_core を実行し、thoughts テーブルへの
    書き込みを SQL で直接検証する。
    """
    session_id = "test_session_999"
    thought = "Thinking about unit tests"

    # thoughts_db は Singleton なので db_conn (knowledge.db) とは別だが、
    # conftest.py が両方を初期化している。
    # thought_logic.process_thought_core は内部で get_thoughts_connection を呼ぶ。

    result = await thought_logic.process_thought_core(
        thought=thought,
        thought_number=1,
        total_thoughts=1,
        next_thought_needed=False,
        session_id=session_id,
        agent_id="thought_tester",
    )

    assert result["thoughtNumber"] == 1
    assert result["totalThoughts"] == 1

    # 裏取り (Thoughts DB)
    from shared_memory.infra.database import async_get_thoughts_connection

    async with await async_get_thoughts_connection() as t_conn:
        cursor = await t_conn.execute(
            "SELECT * FROM thought_history WHERE session_id=?", (session_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["thought"] == thought
        assert row["agent_id"] == "thought_tester"
