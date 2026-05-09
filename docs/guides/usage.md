# Usage Guide

SharedMemoryServer can be deployed as a local process or a centralized team hub.

## 1. Prerequisites
- Python 3.10+
- `uv` (recommended)
- Gemini API Key (`GOOGLE_API_KEY`)

## 2. Installation
```bash
git clone https://github.com/ayato-labs/SharedMemoryServer.git
cd SharedMemoryServer
uv pip install -e .
```

## 3. Configuration
Set your environment variables in a `.env` file:
```env
GOOGLE_API_KEY=your_key_here
LOG_LEVEL=INFO
```

## 4. Deployment Modes

### Mode A: Centralized Team Hub (SSE - Recommended)
Run as a persistent server to share memory across multiple developers and devices.
```bash
uv run shared-memory --sse --port 8377 --host 0.0.0.0
```
**Client Configuration:**
```json
"SharedMemoryServer": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "http://<server-ip>:8377/sse"]
}
```

### Mode B: Local Isolation (STDIO)
Standard MCP connection for single-user environments.
```bash
uv run shared-memory
```

## 5. Core Tools
- `read_memory`: Hybrid retrieval (Vector + Graph).
- `save_memory`: Persistent state recording.
- `synthesize_entity`: Summarize architectural state.
- `sequential_thinking`: Deep reasoning context.

---
*See [Operations Manual](operations.md) for troubleshooting and maintenance.*
