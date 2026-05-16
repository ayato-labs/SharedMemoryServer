import json
import httpx

def test_tool():
    url = "http://localhost:8377/mcp"
    headers = {"Accept": "application/json, text/event-stream"}
    
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    
    with httpx.Client() as client:
        print("Sending initialize...")
        resp1 = client.post(url, json=init_payload, headers=headers)
        print(f"Init Status: {resp1.status_code}")
        
        session_id = resp1.headers.get("mcp-session-id")
        print(f"Session ID: {session_id}")
        
        if not session_id:
            print("No session ID found!")
            return
            
        tool_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "read_memory",
                "arguments": {
                    "query": "test"
                }
            }
        }
        
        # Try sending session ID as header
        tool_headers = {
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id
        }
        
        print("\nSending tools/call...")
        resp2 = client.post(url, json=tool_payload, headers=tool_headers)
        print(f"Tool Status: {resp2.status_code}")
        print("Response Content:")
        print(resp2.text)

if __name__ == "__main__":
    test_tool()
