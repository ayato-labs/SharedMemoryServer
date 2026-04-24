import asyncio
import logging
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dogfood-client")

async def run_dogfood():
    server_url = "http://127.0.0.1:8377/sse"
    logger.info(f"Connecting to SharedMemoryServer at {server_url}...")
    
    try:
        async with sse_client(server_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                logger.info("Connection initialized.")
                
                # 1. Save Memory (FIXED: observations as list of dicts)
                logger.info("Step 1: Saving a 'DogfoodingNode' entity...")
                save_result = await session.call_tool("save_memory", {
                    "entities": [
                        {
                            "name": "DogfoodingNode",
                            "entity_type": "concept",
                            "description": "An entity created during automated SSE dogfooding test."
                        }
                    ],
                    "observations": [
                        {"entity": "DogfoodingNode", "content": "This node was created by an automated client test."}
                    ]
                })
                
                if save_result.isError:
                    logger.error(f"FAILURE: save_memory returned error: {save_result.content}")
                    return
                
                logger.info(f"Save Result: {save_result.content[0].text}")
                
                # 2. Read Memory
                logger.info("Step 2: Verifying persistence via read_memory...")
                read_result = await session.call_tool("read_memory", {"query": "DogfoodingNode"})
                content_text = read_result.content[0].text
                
                if "DogfoodingNode" in content_text:
                    logger.info("SUCCESS: DogfoodingNode found in search results.")
                else:
                    logger.error(f"FAILURE: DogfoodingNode NOT found. Result: {content_text}")
                    return

                # 3. Activation Lifecycle
                logger.info("Step 3: Deactivating the entity...")
                await session.call_tool("manage_knowledge_activation", {
                    "ids": ["DogfoodingNode"],
                    "status": "inactive"
                })
                
                logger.info("Step 4: Verifying it's hidden...")
                hidden_result = await session.call_tool("read_memory", {"query": "DogfoodingNode"})
                if "DogfoodingNode" not in hidden_result.content[0].text:
                    logger.info("SUCCESS: Entity is correctly hidden.")
                else:
                    logger.error("FAILURE: Entity is still visible.")

                # 4. Reactivate
                logger.info("Step 5: Reactivating...")
                await session.call_tool("manage_knowledge_activation", {
                    "ids": ["DogfoodingNode"],
                    "status": "active"
                })
                
                logger.info("Dogfooding lifecycle test COMPLETED SUCCESSFULY.")

    except Exception as e:
        logger.error(f"Error during dogfooding: {e}")

if __name__ == "__main__":
    asyncio.run(run_dogfood())
