import asyncio
import sys
import json
from typing import Optional
from mcp.client.sse import sse_client
from mcp.types import JSONRPCMessage
from mcp.shared.session import SessionMessage
from ripen.common.utils import get_logger

logger = get_logger("proxy")

async def run_stdio_proxy(hub_url: str):
    """
    Acts as a transparent bridge between an MCP Client (like Gemini CLI via stdio)
    and the central Ripen Hub (via SSE).
    """
    logger.info(f"Connecting to Ripen Hub at {hub_url}...")
    
    try:
        # Use the official MCP SSE client to connect to the Hub
        async with sse_client(f"{hub_url}/sse") as (read_stream, write_stream):
            logger.info("Connected to Ripen Hub. Bridging to stdio...")
            
            # We want to forward everything from stdio to the Hub
            # and everything from the Hub back to stdio.
            
            async def forward_from_hub_to_stdio():
                try:
                    async for message in read_stream:
                        # Write the raw message to stdout as a JSON line
                        if isinstance(message, Exception):
                            logger.error(f"Error from Hub stream: {message}")
                            continue
                        
                        # message is a SessionMessage wrapping a JSONRPCMessage
                        # We extract the JSONRPCMessage and dump it to JSON
                        sys.stdout.write(message.message.model_dump_json(by_alias=True, exclude_none=True) + "\n")
                        sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Hub-to-Stdio bridge failed: {e}")

            async def forward_from_stdio_to_hub():
                try:
                    # Read lines from stdin
                    while True:
                        line = await asyncio.get_event_loop().run_in_executor(
                            None, sys.stdin.readline
                        )
                        if not line:
                            break
                        
                        try:
                            # Forward the raw JSON line to the Hub's write stream
                            # This handles the POST request to the Hub automatically
                            from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCNotification, JSONRPCResponse
                            
                            data = json.loads(line)
                            
                            # Wrap in mcp SDK's expected types
                            msg_obj = JSONRPCMessage.model_validate(data)
                            session_msg = SessionMessage(message=msg_obj)
                            
                            await write_stream.send(session_msg)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON received from stdio: {line.strip()}")
                        except Exception as e:
                            logger.error(f"Error forwarding to Hub: {e}")
                except Exception as e:
                    logger.error(f"Stdio-to-Hub bridge failed: {e}")

            # Run both directions concurrently
            await asyncio.gather(
                forward_from_hub_to_stdio(),
                forward_from_stdio_to_hub()
            )
            
    except Exception as e:
        logger.error(f"Proxy failed: {e}")
        # In a real proxy, we might want to retry or exit gracefully
        sys.exit(1)
