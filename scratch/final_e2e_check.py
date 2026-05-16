
import asyncio
import json
import sys
import httpx
from mcp.client.sse import sse_client
from mcp.shared.session import SessionMessage
from mcp.types import JSONRPCMessage

async def test_e2e_connection(hub_url: str):
    print(f"--- STARTING E2E TEST -> {hub_url} ---")
    
    # 1. Health Check
    print(f"Step 1: HTTP GET {hub_url}/sse")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{hub_url}/sse")
            print(f"  Result: {resp.status_code}")
            if resp.status_code != 200:
                print("  FAILED: Hub returned non-200")
                return
        except Exception as e:
            print(f"  FAILED: {e}")
            return

    # 2. SSE Stream Connection
    print(f"Step 2: Establishing SSE Stream...")
    try:
        async with sse_client(f"{hub_url}/sse") as (read_stream, write_stream):
            print("  SUCCESS: Stream connected.")
            
            # 3. Sending Mock Request
            print("Step 3: Sending 'initialize' request...")
            init_req = {
                "jsonrpc": "2.0", 
                "method": "initialize", 
                "params": {
                    "protocolVersion": "2024-11-05", 
                    "capabilities": {}, 
                    "clientInfo": {"name": "e2e-test", "version": "1.0"}
                }, 
                "id": 1001
            }
            
            msg_obj = JSONRPCMessage.model_validate(init_req)
            session_msg = SessionMessage(message=msg_obj)
            
            print("  Sending to write_stream...")
            await write_stream.send(session_msg)
            print("  Sent successfully.")
            
            # 4. Waiting for Response
            print("Step 4: Waiting for response from Hub...")
            async for message in read_stream:
                print(f"  RECEIVED: {message.message}")
                if hasattr(message.message, 'id') and message.message.id == 1001:
                    print("  SUCCESS: Received matching response!")
                    break
                else:
                    print("  Ignoring unrelated message.")
                    
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    hub = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8378"
    asyncio.run(test_e2e_connection(hub))
