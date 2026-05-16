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
                "name": "sequential_thinking",
                "arguments": {
                    "thought": "Testing sequential thinking via Streamable HTTP",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        
        tool_headers = {
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id
        }
        
        print("\nSending tools/call for sequential_thinking...")
        resp2 = client.post(url, json=tool_payload, headers=tool_headers)
        print(f"Tool Status: {resp2.status_code}")
        print("Response Content:")
        print(resp2.text)

if __name__ == "__main__":
    test_tool()
