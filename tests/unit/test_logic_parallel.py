from unittest.mock import patch

import pytest

from shared_memory import logic


@pytest.mark.unit
class TestLogicParallel:
    @pytest.mark.asyncio
    async def test_save_memory_core_parallel_grouping(self, fake_llm):
        """
        Tests that save_memory_core correctly groups observations by entity
        and triggers parallel conflict checks.
        """
        # We will patch graph.check_conflict to track how many times it's called
        # and what arguments it receives.
        # Since this is a unit test, we can use patch, but we avoid MagicMocking 
        # the ENTIRE client. We just want to see the batching.
        
        call_args = []
        
        async def mock_check_conflict(entity_name, new_contents, agent_id, conn=None):
            call_args.append((entity_name, new_contents))
            # Just return no conflicts
            return [(False, "No conflict")] * len(new_contents)

        with patch("shared_memory.logic.graph.check_conflict", side_effect=mock_check_conflict):
            observations = [
                {"entity_name": "Entity1", "content": "Fact 1.1"},
                {"entity_name": "Entity2", "content": "Fact 2.1"},
                {"entity_name": "Entity1", "content": "Fact 1.2"},
                {"entity_name": "Entity3", "content": "Fact 3.1"},
            ]
            
            await logic.save_memory_core(observations=observations, agent_id="test_agent")
            
            # Should have 3 calls (Entity1, Entity2, Entity3)
            assert len(call_args) == 3
            
            # Check Entity1 call - should have 2 contents
            entity1_call = next(arg for arg in call_args if arg[0] == "Entity1")
            assert len(entity1_call[1]) == 2
            assert "Fact 1.1" in entity1_call[1]
            assert "Fact 1.2" in entity1_call[1]
            
            # Check others have 1 content
            assert any(arg[0] == "Entity2" and len(arg[1]) == 1 for arg in call_args)
            assert any(arg[0] == "Entity3" and len(arg[1]) == 1 for arg in call_args)

    @pytest.mark.asyncio
    async def test_save_memory_core_with_actual_conflicts(self, fake_llm):
        """
        Tests that conflicts are correctly reported when the batch check finds them.
        """
        async def mock_check_conflict_with_fail(entity_name, new_contents, agent_id, conn=None):
            if entity_name == "ConflictEntity":
                return [(True, "Internal Conflict Found")] * len(new_contents)
            return [(False, "No conflict")] * len(new_contents)

        with patch(
            "shared_memory.logic.graph.check_conflict", side_effect=mock_check_conflict_with_fail
        ):
            observations = [
                {"entity_name": "SafeEntity", "content": "Safe fact"},
                {"entity_name": "ConflictEntity", "content": "Bad fact"},
            ]
            
            result = await logic.save_memory_core(observations=observations, agent_id="test_agent")
            
            assert "CONFLICTS DETECTED" in result
            assert "ConflictEntity" in result
            assert "Internal Conflict Found" in result
            assert "SafeEntity" not in result
