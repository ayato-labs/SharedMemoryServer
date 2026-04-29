import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from shared_memory.core import logic
import aiosqlite


@pytest.mark.asyncio
async def test_memory_saving_pipeline_with_db_lock_retry():
    """
    Test that real_init_db correctly retries when encountering a DB lock.
    """
    from shared_memory.infra.database import init_db as real_init_db
    
    # We patch _async_get_connection_raw which is called by init_db.
    # It returns an AsyncSQLiteConnection object which is awaited to get a connection.
    
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=MagicMock())
    mock_conn.commit = AsyncMock()
    mock_conn.close = AsyncMock()
    # Mock row_factory
    mock_conn.row_factory = None
    
    # The AsyncSQLiteConnection context manager:
    # async with await _async_get_connection_raw(...) as conn:
    
    mock_wrapper = MagicMock()
    mock_wrapper.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_wrapper.__aexit__ = AsyncMock()
    
    # We need to mock 'await _async_get_connection_raw(...)'
    # Since it's an async function, we patch it with a function that returns the wrapper.
    async def mock_get_conn_raw(*args, **kwargs):
        return mock_wrapper

    with patch("shared_memory.infra.database._async_get_connection_raw", side_effect=mock_get_conn_raw) as mock_patch:
        # Now we make the context manager fail
        mock_wrapper.__aenter__.side_effect = [
            aiosqlite.OperationalError("database is locked"),
            aiosqlite.OperationalError("database is locked"),
            mock_conn
        ]
        
        with patch("shared_memory.infra.database.asyncio.sleep", return_value=None):
            # This should trigger the decorator on init_db
            await real_init_db(force=True)
            # 3 attempts (2 fails, 1 success)
            assert mock_patch.call_count == 3

@pytest.mark.asyncio
async def test_memory_saving_pipeline_ai_rotation_true_integration():
    """
    Truer integration test: Mock client to fail, let decorator handle retry.
    """
    entities = [{"name": "A", "description": "desc"}]
    
    with patch("shared_memory.infra.embeddings.get_gemini_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client.aio.models.embed_content = AsyncMock()
        mock_client.aio.models.embed_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED"),
            MagicMock(embeddings=[MagicMock(values=[0.1]*768)])
        ]
        mock_client_factory.return_value = mock_client
        
        with patch("shared_memory.infra.database.async_get_connection") as mock_conn_factory:
             mock_conn = MagicMock()
             mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
             mock_conn.__aexit__ = AsyncMock()
             mock_conn_factory.return_value = mock_conn
             
             with patch("shared_memory.core.graph.save_entities", return_value="Saved 1 entities"):
                 with patch("shared_memory.core.ai_control.asyncio.sleep", return_value=None):
                     result = await logic.save_memory_core(entities=entities)
                     assert "Saved 1 entities" in result
                     assert mock_client.aio.models.embed_content.call_count == 2

@pytest.mark.asyncio
async def test_memory_saving_pipeline_partial_failure():
    """
    Test the pipeline when one part (e.g. embeddings) fails.
    """
    entities = [{"name": "FailEntity", "description": "Fail"}]
    
    with patch("shared_memory.core.logic.compute_embeddings_bulk") as mock_emb:
        mock_emb.side_effect = Exception("Embedding Service Unavailable")
        
        result = await logic.save_memory_core(entities=entities)
        
        assert "AI Error" in result
        assert "Embedding Service Unavailable" in result
