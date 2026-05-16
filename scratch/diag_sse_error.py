import asyncio
import json
import sys
from mcp.client.sse import sse_client

async def test_sse_error():
    # Attempt to connect to a non-existent or failing Hub
    hub_url = "http://localhost:8377/sse"
    print(f"Connecting to {hub_url}...")
    try:
        async with sse_client(hub_url) as (read_stream, write_stream):
            print("Connected. Waiting for messages...")
            async for message in read_stream:
                print(f"Received: {type(message)} | {message}")
                if hasattr(message, 'message'):
                    print(f"  Content: {message.message}")
                else:
                    print(f"  NO MESSAGE ATTR")
    except Exception as e:
        print(f"Caught top-level exception: {type(e)} | {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sse_error())
