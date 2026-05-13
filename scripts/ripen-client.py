import asyncio
import json
import sys
import argparse
import httpx
from mcp.client.sse import sse_client
from mcp.shared.session import SessionMessage
from mcp.types import JSONRPCMessage

async def run_bridge(hub_url: str):
    """
    A lightweight, standalone stdio-to-SSE bridge.
    Requires only 'mcp' and 'httpx'.
    No database, no LLM, no business logic.
    """
    sys.stderr.write(f"\n[Ripen Client] Connecting to {hub_url}...\n")
    
    try:
        async with sse_client(hub_url) as (read_stream, write_stream):
            sys.stderr.write("[Ripen Client] Connected! Bridge is active.\n")
            
            async def forward_from_hub_to_stdio():
                try:
                    async for message in read_stream:
                        # Extract the inner JSON-RPC message and dump it to stdout
                        sys.stdout.write(message.message.model_dump_json(by_alias=True, exclude_none=True) + "\n")
                        sys.stdout.flush()
                except Exception as e:
                    sys.stderr.write(f"[Ripen Client] Hub -> Stdio Error: {e}\n")

            async def forward_from_stdio_to_hub():
                try:
                    while True:
                        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                        if not line:
                            break
                        
                        raw_msg = json.loads(line)
                        # Re-wrap in SessionMessage for the Hub
                        rpc_msg = JSONRPCMessage.model_validate(raw_msg)
                        session_msg = SessionMessage(message=rpc_msg)
                        await write_stream.send(session_msg)
                except Exception as e:
                    sys.stderr.write(f"[Ripen Client] Stdio -> Hub Error: {e}\n")

            await asyncio.gather(
                forward_from_hub_to_stdio(),
                forward_from_stdio_to_hub()
            )
    except Exception as e:
        sys.stderr.write(f"[Ripen Client] Connection Failed: {e}\n")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ripen Lightweight Stdio-to-SSE Bridge")
    parser.add_argument("hub_url", help="URL of the central Ripen Hub (e.g., http://192.168.1.50:8377/sse)")
    args = parser.parse_args()
    
    hub_url = args.hub_url
    if not hub_url.endswith("/sse"):
        hub_url = hub_url.rstrip("/") + "/sse"
        
    try:
        asyncio.run(run_bridge(hub_url))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
