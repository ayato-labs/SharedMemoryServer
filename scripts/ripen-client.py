import argparse
import asyncio
import json
import os
import sys

from mcp.client.sse import sse_client
from mcp.shared.session import SessionMessage
from mcp.types import JSONRPCMessage


async def run_bridge(candidates: list[str]):
    """
    A lightweight, standalone stdio-to-SSE bridge with Adaptive Discovery.
    Tries each candidate URL until a connection is established.
    """
    for hub_url in candidates:
        target_url = hub_url
        if not hub_url.endswith("/sse"):
            target_url = hub_url.rstrip("/") + "/sse"
            
        sys.stderr.write(f"[Ripen Client] Attempting to connect to {target_url}...\n")
        
        try:
            # Use a short timeout for the connection phase
            async with asyncio.timeout(5.0):
                async with sse_client(target_url) as (read_stream, write_stream):
                    sys.stderr.write(f"[Ripen Client] Connected to Hub at {target_url}!\n")
                    
                    async def forward_from_hub_to_stdio():
                        try:
                            async for message in read_stream:
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
                                
                                try:
                                    raw_msg = json.loads(line)
                                    rpc_msg = JSONRPCMessage.model_validate(raw_msg)
                                    session_msg = SessionMessage(message=rpc_msg)
                                    # Add timeout for sending
                                    await asyncio.wait_for(write_stream.send(session_msg), timeout=30.0)
                                except Exception as e:
                                    sys.stderr.write(f"[Ripen Client] Send Error: {e}\n")
                        except Exception as e:
                            sys.stderr.write(f"[Ripen Client] Stdio -> Hub Error: {e}\n")

                    await asyncio.gather(
                        forward_from_hub_to_stdio(),
                        forward_from_stdio_to_hub()
                    )
                    return # Exit after successful bridge session
                    
        except (TimeoutError, Exception) as e:
            sys.stderr.write(f"[Ripen Client] Connection to {hub_url} failed: {e}. Trying next...\n")
            continue

    sys.stderr.write("[Ripen Client] All candidates failed. Please ensure a Ripen Hub is running.\n")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ripen Lightweight Adaptive Bridge")
    parser.add_argument("hub_url", nargs="?", help="Primary Ripen Hub URL")
    args = parser.parse_args()
    
    # 1. Collect candidates
    candidates = []
    
    # Env priority
    env_url = os.environ.get("RIPEN_HUB_URL")
    if env_url:
        candidates.append(env_url)
        
    # Positional arg
    if args.hub_url:
        candidates.append(args.hub_url)
        
    # Local fallback
    local_url = "http://localhost:8377"
    if local_url not in candidates:
        candidates.append(local_url)
        
    try:
        asyncio.run(run_bridge(candidates))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
