import json
import httpx
import sys

def test_connection():
    url = "http://localhost:8377/mcp"
    print(f"Connecting to {url}...")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    headers = {"Accept": "application/json, text/event-stream"}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
        print(f"Status Code: {response.status_code}")
        print("Response Content:")
        print(response.text)
        
        if response.status_code == 200:
            print("\nSuccess! Connection established.")
        else:
            print("\nFailed to connect or unexpected status code.")
            
    except Exception as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    test_connection()
