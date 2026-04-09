import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except:
            pass
    for ext in ["-wal", "-shm"]:
        if os.path.exists(path + ext):
            try:
                os.remove(path + ext)
            except:
                pass


@pytest.fixture
def temp_bank():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


@pytest.fixture
def temp_home():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


@pytest.fixture(autouse=True)
def mock_env(temp_db, temp_bank, temp_home):
    """Mocks environment variables for testing with strict isolation."""
    env_vars = {
        "MEMORY_DB_PATH": temp_db,
        "MEMORY_BANK_DIR": temp_bank,
        "THOUGHTS_DB_PATH": temp_db.replace(".db", "_thoughts.db"),
        "SHARED_MEMORY_HOME": temp_home,
    }
    if "GOOGLE_API_KEY" not in os.environ:
        env_vars["GOOGLE_API_KEY"] = "mock_key"

    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture(autouse=True)
async def setup_teardown_db():
    from shared_memory.database import init_db
    from shared_memory.thought_logic import init_thoughts_db
    await init_db()
    await init_thoughts_db()
    yield


@pytest.fixture(autouse=True)
def mock_gemini():
    patches = [
        patch("shared_memory.embeddings.get_gemini_client"),
        patch("shared_memory.search.get_gemini_client"),
        patch("shared_memory.management.get_gemini_client"),
        patch("shared_memory.distiller.get_gemini_client"),
        patch("shared_memory.graph.get_gemini_client"),
    ]
    mock_client = MagicMock()
    mock_embedding_result = MagicMock()
    mock_embedding_result.embeddings = [MagicMock(values=[0.1] * 768)]
    mock_client.models.embed_content.return_value = mock_embedding_result
    mock_client.models.generate_content.return_value = MagicMock(
        text='{"conflict": true, "reason": "Conflict detected.", "synthesis": "Synthesis result."}'
    )
    mock_client.models.list.return_value = [type("Model", (), {"name": "models/gemini-pro"})]
    handlers = []
    for p in patches:
        h = p.start()
        h.return_value = mock_client
        handlers.append(p)
    yield mock_client
    for p in handlers:
        p.stop()


@pytest.fixture
async def async_db(temp_db):
    from shared_memory.database import async_get_connection, init_db
    await init_db()
    async with await async_get_connection() as conn:
        yield conn
