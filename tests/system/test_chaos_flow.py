from unittest.mock import MagicMock, patch

import pytest

from ripen.api import server


@pytest.mark.asyncio
async def test_chaos_failure_resilience():
    """
    Intentionally harsh system test:
    - Triggers DB locks during tools.
    - Triggers AI Quotas.
    - Verifies system remains stable.
    """
    # 1. Setup - Ensure server is clean
    await server.ensure_initialized()

    # 2. Chaos: Mock DB connection to fail with lock intermittently
    call_count = 0

    async def chaotic_conn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            # Every odd call fails
            raise Exception("database is locked")
        # Every even call succeeds (simplistic mock)
        # Note: In real life we'd need a real connection, but we are testing the retry loop
        from aiosqlite import connect

        from ripen.common.utils import get_db_path

        return await connect(get_db_path())

    # We patch at the infra level to affect all tools
    with patch("ripen.infra.database.aiosqlite.connect", side_effect=chaotic_conn):
        # 3. Execution: Save memory should retry and eventually succeed
        # We need a small backoff for the test to finish quickly
        with patch("ripen.infra.database.asyncio.sleep", return_value=None):
            # We also need to mock embeddings to not hit quota yet
            with patch("ripen.infra.embeddings.compute_embeddings_bulk", return_value=[]):
                # Using a higher level save_memory_core directly since
                # server.save_memory is fire-and-forget
                from ripen.core.logic import save_memory_core

                # Mocking graph.save_entities to avoid actual DB write on odd attempts
                with patch(
                    "ripen.core.graph.save_entities", return_value="Saved 1 entities"
                ):
                    result = await save_memory_core(entities=[{"name": "ChaosEntity"}])
                    assert "Saved 1 entities" in result

    # 4. Chaos: AI Quota Failure during Thinking
    # Set engine to gemini to ensure it uses the client
    with patch.dict("os.environ", {"EMBEDDING_ENGINE": "gemini", "GOOGLE_API_KEY": "fake_key"}):
        with patch("ripen.core.ai_control.AIRateLimiter.throttle", return_value=None):
            with patch("ripen.infra.embeddings.get_gemini_client") as mock_client_factory:
                # We need to mock BOTH sync and async embed_content potentially,
                # or ensure we are patching the right place.
                # actually compute_embeddings_bulk uses get_gemini_client().aio.models.embed_content
                mock_client = MagicMock()
                mock_client.aio.models.embed_content.side_effect = [
                    Exception("429 RESOURCE_EXHAUSTED"),
                    MagicMock(embeddings=[MagicMock(values=[0.1] * 768)]),
                ]
                mock_client_factory.return_value = mock_client

                # Ensure we patch time.sleep/asyncio.sleep in ai_control where retry happens
                with patch("ripen.core.ai_control.asyncio.sleep", return_value=None):
                    # sequential_thinking returns JSON
                    res_raw = await server.sequential_thinking(
                        thought="Chaos thought",
                        thought_number=1,
                        total_thoughts=1,
                        next_thought_needed=False,
                    )
                    import json

                    res = json.loads(res_raw)
                    assert "thoughtNumber" in res
                    # Verify it called embeddings at least twice (1st fail, 2nd success)
                    assert mock_client.aio.models.embed_content.call_count >= 2

    # 5. Cleanup
    from ripen.infra.database import close_all_connections

    await close_all_connections()
