import asyncio
import httpx
import json
import sys
import re

async def test_permissive():
    url = "http://127.0.0.1:8378"
    print(f"Testing Permissive Handshake on {url}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Connect to SSE and get session ID
        async with client.stream("GET", f"{url}/sse") as response:
            print(f"SSE Status: {response.status_code}")
            
            # Read first few lines to get session ID
            session_id = None
            async for line in response.aiter_lines():
                if line.startswith("event: endpoint"):
                    # Next line should be data: ...?sessionId=...
                    continue
                if line.startswith("data:"):
                    # Extract sessionId from data URL
                    match = re.search(r"sessionId=([a-zA-Z0-9-]+)", line)
                    if match:
                        session_id = match.group(1)
                        print(f"Found Session ID: {session_id}")
                        break
            
            if not session_id:
                print("Failed to find session ID in SSE stream")
                return

            # Step 2: Send tools/list WITHOUT initialize
            post_url = f"{url}/?sessionId={session_id}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            print(f"Sending tools/list to {post_url} without initialize...")
            r = await client.post(post_url, json=payload)
            print(f"Response Status: {r.status_code}")
            print(f"Response Body: {r.text}")
            
            if r.status_code == 200 and "result" in r.text:
                print("SUCCESS: Permissive Handshake worked!")
            else:
                print("FAILURE: Permissive Handshake did not work as expected.")

if __name__ == "__main__":
    asyncio.run(test_permissive())
