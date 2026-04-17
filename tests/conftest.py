import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.fake_client import FakeGeminiClient


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    for ext in ["-wal", "-shm"]:
        if os.path.exists(path + ext):
            try:
                os.remove(path + ext)
            except Exception:
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
def mock_gemini_globally(request):
    """Globally mocks Gemini API to prevent network calls and hangs during tests."""
    if "no_global_mock" in request.keywords:
        yield None
        return

    fake_client = FakeGeminiClient()
    with patch("google.genai.Client", return_value=fake_client):
        with patch(
            "shared_memory.embeddings.get_gemini_client", return_value=fake_client
        ):
            with patch(
                "shared_memory.graph.get_gemini_client", return_value=fake_client
            ):
                yield fake_client


@pytest.fixture(autouse=True)
async def setup_teardown_db(request):
    from shared_memory.database import AsyncSQLiteConnection, init_db
    from shared_memory.thought_logic import init_thoughts_db

    # Skip auto-initialization for migration tests in test_database.py
    if "test_database.py" in str(request.node.fspath):
        yield
        return

    await init_db(force=True)
    await init_thoughts_db(force=True)
    yield
    # Aggressively close ALL tracked connections to prevent hangs
    try:
        await AsyncSQLiteConnection.close_all_active()
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def cleanup_tasks():
    """Cancel all pending tasks to prevent event loop hangs."""
    yield
    import asyncio
    import logging

    # Disable logging during cleanup to avoid noise
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    if not tasks:
        return

    for t in tasks:
        t.cancel()

    # Use a minimal timeout and ensure we don't hang in the cleanup itself.
    # In CI, we prioritize finishing the job over deep cleanup if it hangs.
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=1.0
        )
    except (TimeoutError, Exception):
        # Force progress even if cleanup hangs
        pass


@pytest.fixture(autouse=True)
def mock_gemini(request):
    if "no_global_mock" in request.keywords:
        yield None
        return

    patches = [
        patch("shared_memory.embeddings.get_gemini_client"),
        patch("shared_memory.search.get_gemini_client"),
        patch("shared_memory.management.get_gemini_client"),
        patch("shared_memory.distiller.get_gemini_client"),
        patch("shared_memory.graph.get_gemini_client"),
    ]
    mock_client = MagicMock()

    def mock_embed_content(model, contents, config=None):
        if isinstance(contents, str):
            n = 1
        else:
            n = len(contents)
        res = MagicMock()
        res.embeddings = [MagicMock(values=[0.1] * 768) for _ in range(n)]
        return res

    mock_client.models.embed_content.side_effect = mock_embed_content
    mock_client.models.generate_content.return_value = MagicMock(
        text=(
            '{"conflict": true, "reason": "Conflict detected.", '
            '"synthesis": "Synthesis result."}'
        )
    )
    mock_client.models.list.return_value = [
        type("Model", (), {"name": "models/gemini-2.0-flash-exp"})
    ]
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


def pytest_sessionfinish(session, exitstatus):
    """
    Cache the test run exit status.
    This ensures we don't accidentally report 'success' if tests failed.
    """
    session.config._ci_exitstatus = exitstatus


def pytest_unconfigure(config):
    """
    Aggressive zombie-thread killer.
    Runs after all tests and coverage reporting have completely finished.
    If we are on CI, bypass Python's atexit and thread-join locks.
    """
    exitstatus = getattr(config, "_ci_exitstatus", 0)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        import sys

        print(
            f"\n[pytest] Tests finished with status {exitstatus}. Forcing os._exit.",
            flush=True,
        )
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(exitstatus))
