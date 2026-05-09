import json
import re
from typing import Any

from ripen.common.utils import get_logger, log_error, log_info
from ripen.core import logic
from ripen.core.ai_control import retry_on_ai_quota
from ripen.infra.llm import get_llm_provider

logger = get_logger("distiller")


@retry_on_ai_quota(max_retries=3)
async def auto_distill_knowledge(session_id: str, thought_history: list[dict[str, Any]]):
    """
    Analyzes thought history using the configured LLM to extract structured knowledge.
    """
    if not thought_history:
        return

    provider = get_llm_provider()

    # 1. Format thoughts for the prompt
    formatted_thoughts = "\n".join(
        [f"Step {t['thought_number']}: {t['thought']}" for t in thought_history]
    )

    prompt = f"""
    Analyze the following thinking process and extract key facts, entities,
    and relations that should be stored in a long-term knowledge graph.

    GUIDELINES:
    - Identify important entities (concepts, people, tools, etc.)
    - Identify relations between these entities.
    - Identify specific observations or facts mentioned.
    - "Simple is best": Focus on high-quality, definite information.
    - Output MUST be valid JSON matching the schema below.

    THINKING PROCESS:
    {formatted_thoughts}

    JSON SCHEMA:
    {{
      "entities": [
        {{
          "name": "Entity Name",
          "entity_type": "type",
          "description": "brief description"
        }}
      ],
      "relations": [
        {{
          "subject": "Subject Entity",
          "object": "Object Entity",
          "predicate": "relation type",
          "justification": "why?"
        }}
      ],
      "observations": [
        {{"entity_name": "Entity Name", "content": "The fact observed"}}
      ]
    }}
    """

    try:
        system_instruction = (
            "You are a high-precision knowledge extraction engine. Output only structured JSON."
        )

        response_text = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
        )

        clean_json = re.sub(r"```json|```", "", response_text).strip()
        extracted_data = json.loads(clean_json)

        # 2. Save extracted knowledge to the graph
        entities = extracted_data.get("entities", [])
        relations = extracted_data.get("relations", [])
        observations = extracted_data.get("observations", [])

        if not (entities or relations or observations):
            log_info(f"No knowledge distilled from session {session_id} (Empty result)")
            return

        # Use default_agent to ensure visibility in audit logs
        await logic.save_memory_core(
            entities=entities,
            relations=relations,
            observations=observations,
            agent_id="default_agent",
        )
        log_info(
            f"Successfully distilled knowledge from session {session_id}: "
            f"{len(entities)} entities, {len(relations)} relations"
        )

    except Exception as e:
        logger.exception(f"Failed to distill knowledge for session {session_id}")
        log_error(f"Failed to distill knowledge for session {session_id}", e)


@retry_on_ai_quota(max_retries=3)
async def incremental_distill_knowledge(session_id: str, thought: str):
    """
    Extracts atomic knowledge from a single thought step (Real-time).
    Runs asynchronously to avoid blocking the reasoning flow.
    """
    provider = get_llm_provider()

    prompt = f"""
    Analyze the following SINGLE THOUGHT from a reasoning process.
    If it contains definite facts, new entities, or relations, extract them.
    If it is just internal monologue or planning without new information, return empty lists.

    THOUGHT:
    {thought}

    OUTPUT FORMAT: Valid JSON matching the schema:
    {{
      "entities": [{{ "name": "Name", "entity_type": "type", "description": "desc" }}],
      "relations": [
        {{ "subject": "A", "object": "B", "predicate": "type", "justification": "why" }}
      ],
      "observations": [{{ "entity_name": "Name", "content": "Fact" }}]
    }}
    """
    try:
        system_instruction = (
            "You are a high-precision knowledge extraction engine. Output only structured JSON."
        )

        response_text = await provider.generate_content(
            prompt=prompt, system_instruction=system_instruction
        )

        clean_json = re.sub(r"```json|```", "", response_text).strip()
        extracted = json.loads(clean_json)

        entities = extracted.get("entities", [])
        relations = extracted.get("relations", [])
        observations = extracted.get("observations", [])

        if entities or relations or observations:
            await logic.save_memory_core(
                entities=entities,
                relations=relations,
                observations=observations,
                agent_id=f"incremental_distiller_{session_id}",
            )
            log_info(f"Incremental Distill: Saved {len(entities) + len(observations)} atoms.")
    except Exception as e:
        logger.exception(f"Incremental distillation failed for {session_id}")
        log_error(f"Incremental distillation failed for {session_id}", e)
