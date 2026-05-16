import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
async def setup_teardown_db(request):
    from loguru import logger

    from ripen.core.thought_logic import init_thoughts_db
    from ripen.infra.database import close_all_connections, init_db

    # Windows Fix: Clear loguru handlers before test to prevent WinError 32 on rotation
    logger.remove()

    # Standard path resolution for testing - Use a more specific prefix
    home_dir = tempfile.mkdtemp(prefix="sm_test_")
    os.environ["SHARED_MEMORY_HOME"] = home_dir
    os.environ["MEMORY_DB_PATH"] = os.path.join(home_dir, "knowledge.db")
    os.environ["THOUGHTS_DB_PATH"] = os.path.join(home_dir, "thoughts.db")
    os.environ["MEMORY_BANK_DIR"] = os.path.join(home_dir, "bank")

    # Initialize databases for each test (Skip for system tests to avoid locking)
    if "system" not in str(request.node.fspath):
        await init_db(force=True)
        await init_thoughts_db(force=True)

        # Reset server initialization state
        from ripen.api import server

        server._INITIALIZED_EVENT = None
        server._INIT_ERROR = None
        server._INIT_STARTED = False
        server._INIT_LOCK = None
    else:
        # Still need to create the directory so env vars point to a valid place
        os.makedirs(os.environ["MEMORY_BANK_DIR"], exist_ok=True)

    # Reset database singletons and locks
    from ripen.infra import database

    database._MAIN_CONNECTION = None
    database._THOUGHTS_CONNECTION = None
    database._INIT_LOCK = None
    database._DB_INITIALIZED = False
    database._WRITE_SEMAPHORES = {}

    # Reset AI control locks
    from ripen.core import ai_control

    ai_control.model_manager._lock = None
    ai_control.AIRateLimiter._locks = {}

    yield

    # Teardown: Close singleton connections before rmtree (Windows requirement)
    try:
        from ripen.api.server import wait_for_background_tasks

        await wait_for_background_tasks(timeout=2.0)
        await close_all_connections()
    except Exception as e:
        print(f"DEBUG: Teardown close_all_connections failed: {e}")

    if os.path.exists(home_dir):
        # Retry logic for Windows rmtree
        for _ in range(10):
            try:
                shutil.rmtree(home_dir, ignore_errors=False)
                break
            except OSError:
                time.sleep(0.2)


@pytest.fixture
def fake_llm_client():
    """Deterministic LLM stub for Unit Tests (No MagicMock)."""
    from ripen.infra.llm import LlmProvider
    from tests.unit.fake_client import FakeGeminiClient

    client = FakeGeminiClient()

    # Wrap client to behave like LlmProvider if needed
    class FakeProvider(LlmProvider):
        async def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
            resp = client.models.generate_content(model="fake", contents=prompt)
            return resp.text

        async def check_health(self) -> bool:
            return True

    provider = FakeProvider()

    patches = [
        patch("ripen.infra.llm.get_llm_provider", return_value=provider),
        patch("ripen.infra.embeddings.get_gemini_client", return_value=client),
    ]

    for p in patches:
        p.start()

    try:
        yield client
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def fake_llm(fake_llm_client):
    """Alias for fake_llm_client for backward compatibility."""
    return fake_llm_client


@contextmanager
def temp_env(env_vars):
    old_env = os.environ.copy()
    os.environ.update(env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


@pytest.fixture
async def uow():
    """Provides a UnitOfWork for the test database."""
    from ripen.infra.uow import UnitOfWork

    async with UnitOfWork() as uow:
        yield uow


@pytest.fixture
async def db_conn(uow):
    """Provides a connection to the test database via UoW."""
    yield uow._conn
