import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
async def setup_teardown_db(request):
    from shared_memory.database import close_all_connections, init_db
    from shared_memory.thought_logic import init_thoughts_db

    # Standard path resolution for testing - Use a more specific prefix
    home_dir = tempfile.mkdtemp(prefix="sm_test_")
    os.environ["SHARED_MEMORY_HOME"] = home_dir
    os.environ["MEMORY_DB_PATH"] = os.path.join(home_dir, "knowledge.db")
    os.environ["THOUGHTS_DB_PATH"] = os.path.join(home_dir, "thoughts.db")
    os.environ["MEMORY_BANK_DIR"] = os.path.join(home_dir, "bank")

    # Initialize databases for each test
    await init_db(force=True)
    await init_thoughts_db(force=True)

    yield

    # Teardown: Close singleton connections before rmtree (Windows requirement)
    await close_all_connections()
    if os.path.exists(home_dir):
        # Retry logic for Windows rmtree
        import time

        for _ in range(5):
            try:
                shutil.rmtree(home_dir, ignore_errors=False)
                break
            except OSError:
                time.sleep(0.1)


@pytest.fixture
def fake_llm():
    """Deterministic LLM stub for Unit Tests (No MagicMock)."""
    from tests.unit.fake_client import FakeGeminiClient

    client = FakeGeminiClient()

    patches = [
        patch("shared_memory.embeddings.get_gemini_client", return_value=client),
        patch("shared_memory.distiller.get_gemini_client", return_value=client),
        patch("shared_memory.graph.get_gemini_client", return_value=client),
    ]

    for p in patches:
        p.start()

    try:
        yield client
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def mock_llm(request):
    """
    Universal LLM mock (MagicMock) for Integration/System tests.
    Disabled automatically if 'fake_llm' fixture or 'use_fake_llm' marker is used.
    """
    if (
        "no_global_mock" in request.node.keywords
        or "use_fake_llm" in request.node.keywords
        or "fake_llm" in request.fixturenames
    ):
        yield None
        return

    client = MagicMock()
    # ... (rest of the MagicMock setup)
    client.models.generate_content.return_value.text = json.dumps(
        {"conflict": False, "reason": "No conflict detected in mock."}
    )

    def set_response(method, text):
        if method == "generate_content":
            client.models.generate_content.return_value.text = text
            client.aio.models.generate_content.return_value.text = text

    client.models.set_response = set_response

    client.aio.models.generate_content = AsyncMock()
    client.aio.models.generate_content.return_value.text = json.dumps(
        {"conflict": False, "reason": "No conflict detected in mock."}
    )

    client.aio.models.embed_content = AsyncMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * 768
    client.aio.models.embed_content.return_value.embeddings = [mock_embedding] * 100

    client.aio.models.list = AsyncMock()
    model_obj = MagicMock()
    model_obj.name = "models/gemini-2.0-flash-exp"
    client.aio.models.list.return_value = [model_obj]

    patches = [
        patch("shared_memory.embeddings.get_gemini_client", return_value=client),
        patch("shared_memory.distiller.get_gemini_client", return_value=client),
        patch("shared_memory.graph.get_gemini_client", return_value=client),
    ]

    for p in patches:
        p.start()

    try:
        yield client
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def mock_gemini_globally(mock_llm):
    return mock_llm


@pytest.fixture(autouse=True)
def mock_gemini(mock_llm):
    return mock_llm


@contextmanager
def temp_env(env_vars):
    old_env = os.environ.copy()
    os.environ.update(env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
