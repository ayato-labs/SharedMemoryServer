import asyncio
import pytest
from unittest.mock import AsyncMock
from shared_memory.ai_control import ModelManager, retry_on_ai_quota, parse_retry_delay
from shared_memory.config import GOOGLE_AI_MODELS

@pytest.mark.unit
class TestAIControl:
    @pytest.mark.asyncio
    async def test_model_manager_rotation(self):
        """Tests that models rotate correctly and detect full cycles."""
        manager = ModelManager()
        models = GOOGLE_AI_MODELS
        
        # Initial model should be the first one
        assert manager.get_current_model() == models[0]
        
        # Rotate through all models
        for i in range(1, len(models)):
            is_full_cycle = await manager.rotate()
            assert is_full_cycle is False
            assert manager.get_current_model() == models[i]
            
        # One more rotation should complete the cycle
        is_full_cycle = await manager.rotate()
        assert is_full_cycle is True
        assert manager.get_current_model() == models[0]

    def test_parse_retry_delay(self):
        """Tests parsing of retry delay from various error formats."""
        # Format 1: Text-based
        exc1 = Exception("Quotas exceeded, retry in 12.5s later.")
        assert parse_retry_delay(exc1) == 12.5
        
        # Format 2: Structured (mocking attribute access)
        class MockError(Exception):
            def __init__(self, message):
                self.message = message
        
        exc2 = MockError({
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "5.2s"
                    }
                ]
            }
        })
        assert parse_retry_delay(exc2) == 5.2
        
        # Format 3: No delay info
        assert parse_retry_delay(Exception("Generic error")) is None

    @pytest.mark.asyncio
    async def test_retry_on_ai_quota_logic(self, fake_llm):
        """
        Tests the retry decorator using the Fake LLM.
        We simulate a 429 error and verify it rotates and eventually succeeds or fails.
        """
        call_count = 0
        
        # Note: We don't use MagicMock for the function itself, just a stateful async function
        @retry_on_ai_quota(max_retries=1, initial_backoff=0.01)
        async def flaking_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                # First call fails with 429
                raise Exception("429 RESOURCE_EXHAUSTED: Too many requests")
            return "Success"

        result = await flaking_function()
        assert result == "Success"
        # 1st attempt (fail) -> 2nd attempt (success)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, fake_llm):
        """Tests that it eventually raises the error after exhausting all retries."""
        call_count = 0
        
        # Max retries = 0 means only 1 cycle of models (if rotate=True)
        # We'll just test a quick exhaustion
        @retry_on_ai_quota(max_retries=0, rotate_models=False)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("429 Persistent Quota Error")

        with pytest.raises(Exception) as excinfo:
            await failing_function()
        assert "429" in str(excinfo.value)
        assert call_count == 1
