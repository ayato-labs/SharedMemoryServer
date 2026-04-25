import json
from typing import Any

from shared_memory import logic
from shared_memory.config import settings
from shared_memory.embeddings import get_gemini_client
from shared_memory.utils import AIRateLimiter, get_logger, log_error, log_info

logger = get_logger("distiller")


async def auto_distill_knowledge(session_id: str, thought_history: list[dict[str, Any]]):
    """
    Analyzes thought history using Gemini to extract structured knowledge.
    """
    if not thought_history:
        return

    client = get_gemini_client()
    if not client:
        log_info(
            f"Cannot distill knowledge for session {session_id}: "
            "Gemini client not initialized (API key missing)"
        )
        return

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
          "source": "Source Name",
          "target": "Target Name",
          "relation_type": "type",
          "justification": "why?"
        }}
      ],
      "observations": [
        {{"entity_name": "Entity Name", "content": "The fact observed"}}
      ]
    }}
    """

    try:
        # Enforce Rate Limiting
        await AIRateLimiter.throttle()

        # Use centralized model from settings
        response = await client.aio.models.generate_content(
            model=settings.generative_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        raw_text = response.text.strip()

        # Strip markdown if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```", 2)[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:].strip()
            raw_text = raw_text.strip()

        extracted_data = json.loads(raw_text)

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
        logger.error(f"Failed to distill knowledge for session {session_id}: {e}", exc_info=True)
        log_error(f"Failed to distill knowledge for session {session_id}", e)
        # Note: We don't re-raise here to avoid crashing the thought process
        # because distillation is a background/secondary task.


async def incremental_distill_knowledge(session_id: str, thought: str):
    """
    Extracts atomic knowledge from a single thought step (Real-time).
    Runs asynchronously to avoid blocking the reasoning flow.
    """
    client = get_gemini_client()
    if not client:
        return

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
        {{ "source": "A", "target": "B", "relation_type": "type", "justification": "why" }}
      ],
      "observations": [{{ "entity_name": "Name", "content": "Fact" }}]
    }}
    """
    try:
        # Enforce Rate Limiting
        await AIRateLimiter.throttle()

        response = await client.aio.models.generate_content(
            model=settings.generative_model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        extracted = json.loads(response.text)

        entities = extracted.get("entities", [])
        relations = extracted.get("relations", [])
        observations = extracted.get("observations", [])

        if entities or relations or observations:
            from shared_memory import logic

            await logic.save_memory_core(
                entities=entities,
                relations=relations,
                observations=observations,
                agent_id=f"incremental_distiller_{session_id}",
            )
            log_info(f"Incremental Distill: Saved {len(entities) + len(observations)} atoms.")
    except Exception as e:
        logger.error(f"Incremental distillation failed for {session_id}: {e}", exc_info=True)
        log_error(f"Incremental distillation failed for {session_id}", e)
