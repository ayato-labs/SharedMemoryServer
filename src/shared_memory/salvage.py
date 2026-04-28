import json
from typing import Any

from shared_memory.config import settings
from shared_memory.embeddings import get_gemini_client
from shared_memory.search import perform_search
from shared_memory.ai_control import AIRateLimiter, retry_on_ai_quota
from shared_memory.utils import get_logger, log_error

logger = get_logger("salvage")


@retry_on_ai_quota(max_retries=3)
async def salvage_related_knowledge(
    thought: str, session_id: str, history: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """
    LLM-driven re-ranking salvage pipeline.
    1. Retrieval: Hybrid search for raw candidates.
    2. Re-rank: Use Gemini to select the most relevant atoms.
    """
    try:
        # 1. Fetch Candidates (Broad Retrieval)
        # Use a high candidate_limit to get enough material for the LLM to filter.
        graph_data, bank_data = await perform_search(thought, candidate_limit=20)

        candidates = []
        # Flatten graph data
        for ent in graph_data.get("entities", []):
            candidates.append({"type": "entity", "id": ent["name"], "content": ent["description"]})
        for obs in graph_data.get("observations", []):
            candidates.append(
                {"type": "observation", "id": obs["entity"], "content": obs["content"]}
            )
        # Flatten bank data
        for filename, content in bank_data.items():
            candidates.append({"type": "bank_file", "id": filename, "content": content[:1000]})

        if not candidates:
            return []

        # 2. Re-rank with LLM
        client = get_gemini_client()
        if not client:
            # Fallback to top 3 raw matches if Gemini is unavailable
            return candidates[:3]

        history_context = ""
        if history:
            history_context = "\n".join(
                [f"Prev Step {t['thought_number']}: {t['thought'][:200]}..." for t in history[-3:]]
            )

        # Enforce Rate Limiting (Generation task)
        await AIRateLimiter.throttle(task_type="generation")

        prompt = f"""
        You are a Knowledge Re-ranking Engine.
        Based on the CURRENT THOUGHT and RECENT HISTORY, select the top 5 most relevant items
        from the CANDIDATE LIST.
        Focus on information that provides critical context, facts, or design patterns
        needed for the current reasoning step.

        CURRENT THOUGHT:
        {thought}

        RECENT HISTORY:
        {history_context}

        CANDIDATE LIST:
        {json.dumps(candidates, ensure_ascii=False)}

        OUTPUT INSTRUCTIONS:
        - Return ONLY a JSON list of the indices (0-based) of the selected items.
        - Maximum 5 items.
        - Example: [0, 5, 12]
        """

        response = await client.aio.models.generate_content(
            model=settings.generative_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        try:
            selected_indices = json.loads(response.text)
            if not isinstance(selected_indices, list):
                return candidates[:3]

            reranked = [candidates[i] for i in selected_indices if 0 <= i < len(candidates)]
            logger.info(
                f"Salvage: Successfully re-ranked {len(reranked)} items for session {session_id}"
            )
            return reranked
        except Exception:
            # Fallback if JSON parsing fails
            logger.error(
                "Salvage: Failed to parse re-rank JSON. Response: %s",
                response.text,
                exc_info=True,
            )
            return candidates[:3]

    except Exception as e:
        logger.error(f"Salvage failure for session {session_id}: {e}", exc_info=True)
        log_error(f"Salvage failure for session {session_id}", e)
        return []
