from unittest.mock import AsyncMock, patch

import pytest

from shared_memory.core.distiller import auto_distill_knowledge


@pytest.mark.asyncio
async def test_auto_distill_knowledge_logging_fix():
    """Verify that auto_distill_knowledge handles AI errors with braces without KeyError."""
    
    # 1. Mock Gemini client to raise a ServerError with braces
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content.side_effect = Exception(
        "500 INTERNAL. {'error': {'code': 500, 'message': 'Internal error encountered.'}}"
    )
    
    with patch("shared_memory.core.distiller.get_gemini_client", return_value=mock_client), \
         patch("shared_memory.core.distiller.AIRateLimiter.throttle", AsyncMock()):
        
        # This should NOT raise KeyError even though the exception string has braces
        # and the code uses logger.exception() or logger.error(..., exc_info=True)
        # (We fixed it to use logger.exception which is safe)
        await auto_distill_knowledge("test_session", [{"thought_number": 1, "thought": "test"}])
        
    # If it reached here without KeyError, it's successful.
