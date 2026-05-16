
import asyncio
import httpx
from mcp.client.sse import sse_client
import logging
import sys

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger("ripen_diag")

async def test_hub_direct():
    url = "http://localhost:8377/sse"
    logger.info(f"Direct Hub Diagnostic: Connecting to {url}")
    
    try:
        async with sse_client(url) as (read_stream, write_stream):
            logger.info("SUCCESS: SSE Connection established.")
            
            # Send initialize
            init_req = {
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ripen-diag", "version": "1.0"}
                },
                "jsonrpc": "2.0",
                "id": 1
            }
            logger.info("Sending initialize request...")
            await write_stream.send(init_req)
            
            logger.info("Waiting for response (5s timeout)...")
            async for message in read_stream:
                logger.info(f"RECEIVED: {message}")
                break
            
            logger.info("Diagnostic complete.")
    except Exception as e:
        logger.error(f"FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_hub_direct())
