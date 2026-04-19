import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from shared_memory.config import Settings

@pytest.mark.asyncio
async def test_settings_db_path_resolution():
    """Verify that db_path is correctly derived from base_dir or env."""
    settings = Settings()
    # First, ensure we clear any pre-set MEMORY_DB_PATH from conftest
    with patch.dict(os.environ, {"SHARED_MEMORY_HOME": "/tmp/sm_test"}, clear=False):
        if "MEMORY_DB_PATH" in os.environ:
            del os.environ["MEMORY_DB_PATH"]
        
        # Reset internal cache for test
        settings._base_dir = None
        assert settings.base_dir == Path("/tmp/sm_test").absolute()
        assert settings.db_path == Path("/tmp/sm_test/knowledge.db").absolute()

    with patch.dict(os.environ, {"MEMORY_DB_PATH": "/tmp/explicit.db"}):
        assert settings.db_path == Path("/tmp/explicit.db").absolute()

@pytest.mark.asyncio
async def test_api_key_priority():
    """Verify Environ > .env > MCP settings priority."""
    settings = Settings()
    
    # 1. Env Var
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "env_key"}):
        settings._api_key = None
        assert settings.api_key == "env_key"

    # 2. MCP Settings fallback
    # Preserve home variables to avoid pathlib.home() breakdown
    safe_env = {k: v for k, v in os.environ.items() if k in ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH")}
    with patch.dict(os.environ, safe_env, clear=True):
        settings._api_key = None
        mcp_json = {
            "mcpServers": {
                "SharedMemoryServer": {
                    "env": {"GOOGLE_API_KEY": "mcp_key"}
                }
            }
        }
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(mcp_json))):
            assert settings.api_key == "mcp_key"

@pytest.mark.asyncio
async def test_logging_flag():
    """Verify logging flag resolution."""
    settings = Settings()
    with patch.dict(os.environ, {"ENABLE_STRUCTURED_LOGGING": "false"}):
        assert settings.enable_structured_logging is False
    with patch.dict(os.environ, {"ENABLE_STRUCTURED_LOGGING": "true"}):
        assert settings.enable_structured_logging is True

import json # For the mock_open usage
