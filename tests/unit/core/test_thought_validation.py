from unittest.mock import AsyncMock, patch

import pytest

from shared_memory.core.thought_logic import process_thought_core


@pytest.mark.unit
@pytest.mark.asyncio
class TestThoughtValidation:
    """
    Tests for thought sequence integrity and branch logic.
    Uses fake_llm for the required accretion/salvage steps.
    """

    async def test_thought_sequence_integrity(self, fake_llm):
        """Tests that thoughts are stored and history increments."""
        session_id = "test_sequence"

        # First thought
        res1 = await process_thought_core(
            thought="Thought 1",
            thought_number=1,
            total_thoughts=2,
            next_thought_needed=True,
            session_id=session_id,
        )
        assert res1["thoughtNumber"] == 1
        assert res1["thoughtHistoryLength"] == 1

        # Second thought
        res2 = await process_thought_core(
            thought="Thought 2",
            thought_number=2,
            total_thoughts=2,
            next_thought_needed=False,
            session_id=session_id,
        )
        assert res2["thoughtNumber"] == 2
        assert res2["thoughtHistoryLength"] == 2

    async def test_revision_validation_failure(self, fake_llm):
        """Tests that revising a non-existent thought returns an error."""
        session_id = "test_revision_fail"

        # Try to revise thought #10 when session is empty
        res = await process_thought_core(
            thought="Revision thought",
            thought_number=1,
            total_thoughts=1,
            next_thought_needed=False,
            is_revision=True,
            revises_thought=10,
            session_id=session_id,
        )

        assert "error" in res
        assert "does not exist" in res["error"]

    async def test_branching_logic(self, fake_llm):
        """Tests that branching from an existing thought works."""
        session_id = "test_branch"

        # 1. Original thought
        await process_thought_core(
            thought="Base thought",
            thought_number=1,
            total_thoughts=5,
            next_thought_needed=True,
            session_id=session_id,
        )

        # 2. Branch from thought 1
        res = await process_thought_core(
            thought="Branch thought",
            thought_number=2,
            total_thoughts=5,
            next_thought_needed=True,
            branch_from_thought=1,
            branch_id="alternative_path",
            session_id=session_id,
        )

        assert res["thoughtNumber"] == 2
        # History length should be 2
        assert res["thoughtHistoryLength"] == 2

    async def test_distillation_trigger(self, fake_llm):
        """Tests that final distillation is triggered when next_thought_needed=False."""
        session_id = "test_distill_trigger"

        with patch(
            "shared_memory.core.distiller.auto_distill_knowledge", new_callable=AsyncMock
        ) as mock_distill:
            await process_thought_core(
                thought="Final thought",
                thought_number=1,
                total_thoughts=1,
                next_thought_needed=False,
                session_id=session_id,
            )
            # Should be called once for final distillation
            mock_distill.assert_called_once()
