from typing import Any

from shared_memory.common.utils import get_logger, log_error
from shared_memory.core.search import perform_search

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
        # Using a limit of 5 to 7 provides sufficient context without overwhelming the client LLM.
        graph_data, bank_data = await perform_search(thought, candidate_limit=7)

        results = []
        # 1. Flatten entities
        for ent in graph_data.get("entities", []):
            results.append({
                "type": "entity",
                "id": ent["name"],
                "content": ent["description"]
            })
        
        # 2. Flatten observations
        for obs in graph_data.get("observations", []):
            results.append({
                "type": "observation",
                "id": f"{obs['entity']}_obs",
                "content": obs["content"]
            })
            
        # 3. Flatten bank files
        for filename, content in bank_data.items():
            results.append({
                "type": "bank_file",
                "id": filename,
                "content": content
            })

        # Final trimming to ensure we don't exceed a reasonable context size
        final_results = results[:7]
        
        logger.info(
            f"Salvage (FastPath): Retrieved {len(final_results)} items for session {session_id}"
        )
        return final_results

    except Exception as e:
        logger.exception("Salvage failure (FastPath) for session {session_id}", 
                         session_id=session_id)
        log_error(f"Salvage failure for session {session_id}", e)
        return []
