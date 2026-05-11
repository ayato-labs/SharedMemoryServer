from typing import Any

from ripen.common.utils import get_logger, log_error
from ripen.core.search import perform_search

logger = get_logger("salvage")


async def salvage_related_knowledge(
    thought: str, session_id: str, history: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """
    High-speed knowledge retrieval pipeline (Fast Path).
    - Bypasses LLM re-ranking to minimize latency.
    - Directly returns top matches from Hybrid Search (Semantic + Keyword).
    """
    try:
        # Fetch Top Candidates (already ranked by Hybrid Search logic in core.search)
        # We EXPLICITLY exclude TRANSIENT logs from automated salvage to prevent noise/hallucination loops.
        graph_data, bank_data = await perform_search(
            thought, candidate_limit=7, include_transient=False
        )

        results = []
        # 1. Flatten troubleshooting (Highest Priority)
        for ts in graph_data.get("troubleshooting", []):
            results.append(
                {"type": "troubleshooting", "id": f"TS-{ts['id']}", "content": ts["solution"]}
            )

        # 2. Flatten entities
        for ent in graph_data.get("entities", []):
            results.append({"type": "entity", "id": ent["name"], "content": ent["description"]})

        # 3. Flatten observations
        for obs in graph_data.get("observations", []):
            results.append(
                {"type": "observation", "id": f"{obs['entity']}_obs", "content": obs["content"]}
            )

        # 4. Flatten bank files
        for filename, content in bank_data.items():
            results.append({"type": "bank_file", "id": filename, "content": content})

        # Final trimming to ensure we don't exceed a reasonable context size
        final_results = results[:7]

        logger.info(
            f"Salvage (FastPath): Retrieved {len(final_results)} high-signal items for session {session_id}"
        )
        return final_results

    except Exception as e:
        logger.exception(
            "Salvage failure (FastPath) for session {session_id}", session_id=session_id
        )
        log_error(f"Salvage failure for session {session_id}", e)
        return []
