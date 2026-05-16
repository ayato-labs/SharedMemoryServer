
import httpx
import asyncio

async def manual_post_test():
    url = "http://localhost:8377/sse"
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Get Session ID
        print(f"Connecting to {url}...")
        try:
            # We use a stream to get the event but we just need the headers/first event
            async with client.stream("GET", url) as response:
                # SSE starts with an 'endpoint' event containing the URL or session_id in the URL
                # In mcp-python-sdk, it's often in the first few bytes
                pass 
            
            # Actually, the previous PowerShell showed session_id is in the location or we can just sniff it from a fresh GET
            # Let's just do a normal GET and see what we get
            resp = await client.get(url)
            # The session ID is usually in the URL we are redirected to or given in the response
            # Let's try to find it in the text if it's not a redirect
            print(f"SSE Response: {resp.status_code}")
            print(f"SSE Headers: {resp.headers}")
            
            # Fallback: Just try a common session ID or wait for the Hub to tell us
            # Actually, let's just use the one from the previous log if we can, or just wait.
            # BETTER: The Hub returns 'event: endpoint\ndata: ...'
            
            # Let's do a proper SSE listen for 1 second
            session_id = None
            async with client.stream("GET", url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = line.replace("data:", "").strip()
                        if "session_id=" in data:
                            session_id = data.split("session_id=")[1]
                            break
                    if session_id: break
            
            if not session_id:
                print("Failed to get session_id")
                return

            print(f"Found Session ID: {session_id}")
            
            # 2. Send POST
            post_url = f"http://localhost:8377/messages/?session_id={session_id}"
            body = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "manual-test", "version": "1.0"}
                },
                "id": 999
            }
            print(f"Sending POST to {post_url}...")
            post_resp = await client.post(post_url, json=body)
            print(f"POST Result: {post_resp.status_code} - {post_resp.text}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(manual_post_test())
