# LLM Infrastructure and Startup Fixes (2026-05-06)

This document records the critical fixes implemented to stabilize the LLM pipeline and the server startup process.

## 1. Ollama '404 Not Found' Error
### Issue
The server failed with `httpx.HTTPStatusError: Client error '404 Not Found' for url 'http://localhost:11434/api/generate'` when attempting knowledge distillation.

### Root Cause
- The specified Ollama model (previously `gemma3:4b`) was not present in the local Ollama environment.
- Lack of clear guidance in logs on how to resolve model-missing errors.

### Resolution
- **Standardized Model**: Updated the default model to `llama3.1` (Llama 3.1 8B), which reliably supports JSON mode.
- **Actionable Logging**: Improved `OllamaProvider` to catch 404 errors and explicitly suggest running `ollama pull <model>`.
- **JSON Mode Force**: Explicitly added `"format": "json"` to Ollama payloads to ensure parseable responses for the distiller.

---

## 2. FastMCP 3.x Compatibility (AttributeError)
### Issue
The server failed to start with `AttributeError: type object 'FastMCP' has no attribute 'sse_app'`.

### Root Cause
`fastmcp` version 3.x introduced breaking changes, replacing `sse_app` with a unified `http_app` and changing the `mcp.run()` configuration pattern.

### Resolution
- **Patched `http_app`**: Updated the manual patching in `server.py` to use `FastMCP.http_app`.
- **Signature Update**: Adjusted the patch to handle `*args` and `**kwargs` to match the new Starlette app factory signature.
- **Port Configuration**: Replaced `mcp.settings.port = args.port` with `mcp.run(transport="sse", port=args.port)`, passing the port directly to the transport layer.

---

## 3. Windows Log Rotation Conflict (PermissionError)
### Issue
The server crashed during initialization with `PermissionError: [WinError 32]` when trying to rotate `server.jsonl`.

### Root Cause
The `loguru` configuration used `rotation=lambda _, __: True`, which forced a file rename on every startup. On Windows, if any process (including the previous instance or a log viewer) holds a handle to the file, the rename fails.

### Resolution
- **Resilient Rotation**: Changed the policy in `utils.py` to `rotation="10 MB"`.
- This avoids renaming the file at the exact moment of startup unless the size threshold is reached, significantly reducing race conditions on Windows.

---

## 4. AttributeError in `save_memory_core`
### Issue
The server crashed with `AttributeError: 'tuple' object has no attribute 'get'` when processing conflict check results.

### Root Cause
`graph.check_conflict` returns a list of `(is_conflict, reason)` tuples, but the logic in `save_memory_core` was treating the result as a dictionary (using `.get("status")`).

### Resolution
- Updated the result processing logic in `logic.py` to correctly unpack the tuple: `is_conflict, reason = res`.

---

## 5. LLM Provider Prioritization
### Optimization
To ensure the system works \"out of the box\" even without local Ollama, the system now automatically prioritizes **Gemini** if a `GOOGLE_API_KEY` is detected in the environment.
