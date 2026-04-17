import asyncio
import os
import sys

# Ensure the src directory is in the path
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory import logic, thought_logic
from shared_memory.database import init_db

async def verify():
    print("Initializing databases...")
    await init_db()
    await thought_logic.init_thoughts_db()

    session_id = f"verify_session_{int(asyncio.get_event_loop().time())}"
    entity_name = "InjectionTestEntity"
    observation_content = "This is a secret knowledge for injection verification."

    print(f"Saving memory for {entity_name}...")
    await logic.save_memory_core(
        entities=[{"name": entity_name, "entity_type": "test", "description": "A test entity"}],
        observations=[{"entity_name": entity_name, "content": observation_content}],
        agent_id="verify_agent"
    )

    print("Executing sequential thinking...")
    # Search for the knowledge just saved
    result = await thought_logic.process_thought_core(
        thought=f"I am thinking about {entity_name}",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_id
    )

    print("\nResult related_knowledge:")
    found = False
    for item in result.get("related_knowledge", []):
        print(f"- Source: {item['source']}, ID: {item['id']}, Score: {item['score']}")
        if "content" in item:
            print(f"  Content: {item['content']}")
            if observation_content in item['content']:
                found = True
        else:
            print("  [ERROR] Content field missing!")

    if found:
        print("\nSUCCESS: Knowledge injection confirmed with content!")
    else:
        print("\nFAILURE: Target knowledge not found or content missing.")

if __name__ == "__main__":
    asyncio.run(verify())
