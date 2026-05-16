import json
import httpx

def list_tools():
    url = "http://localhost:8377/mcp"
    print(f"Connecting to {url} to list tools...")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    headers = {"Accept": "application/json, text/event-stream"}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
        print(f"Status Code: {response.status_code}")
        
        # Parse SSE
        for line in response.text.splitlines():
            if line.startswith("data: "):
                data_str = line[6:]
                data = json.loads(data_str)
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return data
                
    except Exception as e:
        print(f"Error connecting to server: {e}")
    return None

if __name__ == "__main__":
    list_tools()
