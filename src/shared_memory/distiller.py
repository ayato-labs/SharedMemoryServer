import json
from typing import Any

from shared_memory import logic
from shared_memory.embeddings import get_gemini_client
from shared_memory.utils import log_error, log_info


async def auto_distill_knowledge(session_id: str, thought_history: list[dict[str, Any]]):
    """
    Analyzes thought history using Gemini to extract structured knowledge.
    """
    if not thought_history:
        return

    client = get_gemini_client()
    if not client:
        log_info(
            f"Cannot distill knowledge for session {session_id}: Gemini client not initialized (API key missing)"
        )
        return

    # 1. Format thoughts for the prompt
    formatted_thoughts = "\n".join(
        [f"Step {t['thought_number']}: {t['thought']}" for t in thought_history]
    )

    prompt = f"""
    Analyze the following thinking process and extract key facts, entities, and relations 
    that should be stored in a long-term knowledge graph.
    
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
        {{"name": "Entity Name", "entity_type": "type", "description": "brief description"}}
      ],
      "relations": [
        {{"source": "Source Name", "target": "Target Name", "relation_type": "type", "justification": "why?"}}
      ],
      "observations": [
        {{"entity_name": "Entity Name", "content": "The fact observed"}}
      ]
    }}
    """

    try:
        # DYNAMIC MODEL DISCOVERY: Find the correct model name automatically
        try:
            available_models = [m.name for m in client.models.list()]
        except Exception as e:
            log_error(
                f"Failed to list models for session {session_id} (possibly invalid API key)",
                e,
            )
            return

        # Prefer gemini-3.1-flash-lite-preview if exists, else find any flash-lite
        model_name = "gemini-3.1-flash-lite-preview"
        if f"models/{model_name}" in available_models:
            model_name = f"models/{model_name}"
        elif model_name not in available_models:
            # Fallback search
            fallback = [
                m
                for m in available_models
                if "flash" in m.lower() and "lite" in m.lower()
            ]
            model_name = fallback[0] if fallback else "models/gemini-2.0-flash"

        response = client.models.generate_content(
            model=model_name,
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
            f"Successfully distilled knowledge from session {session_id}: {len(entities)} entities, {len(relations)} relations"
        )

    except Exception as e:
        log_error(f"Failed to distill knowledge for session {session_id}", e)
        # Note: We don't re-raise here to avoid crashing the thought process
        # because distillation is a background/secondary task.
