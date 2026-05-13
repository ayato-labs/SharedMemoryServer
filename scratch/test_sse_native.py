import asyncio
import httpx
from mcp.client.sse import sse_client
from mcp.types import JSONRPCMessage, JSONRPCRequest

async def test_sse_native():
    url = "http://localhost:8377/sse"
    print(f"Connecting to {url}...")
    try:
        async with sse_client(url) as (read_stream, write_stream):
            print("Connected! Sending list_tools request...")
            req = JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="tools/list",
                params={}
            )
            
            # The write_stream.send() in mcp.client.sse expects a SessionMessage?
            # Let's check what it expects.
            from mcp.shared.session import SessionMessage
            msg = SessionMessage(message=req)
            await write_stream.send(msg)
            
            print("Request sent. Waiting for response...")
            async for message in read_stream:
                print(f"Received: {message}")
                break
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_sse_native())
