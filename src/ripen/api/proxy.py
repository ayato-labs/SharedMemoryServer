import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Optional
from mcp.client.sse import sse_client
from mcp.types import JSONRPCMessage
from mcp.shared.session import SessionMessage
from ripen.common.utils import get_logger

logger = get_logger("proxy")

# Diagnostic file log - because proxy's loguru logs go to stderr which may get swallowed
DIAG_LOG = Path.home() / ".ripen" / "proxy_diag.log"

def _diag(msg: str):
    """Write diagnostic message to stderr and a file for debugging."""
    # Ensure it goes to stderr so it doesn't corrupt stdout (the MCP bridge)
    print(f"DEBUG: {msg}", file=sys.stderr)
    try:
        with open(DIAG_LOG, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


async def run_stdio_proxy(team_url: Optional[str] = None):
    """
    Acts as a transparent bridge between an MCP Client and the Ripen Hub.
    Automatically tries Team Hub first, then falls back to Local Hub.
    """
    # Clear previous diag log
    try:
        DIAG_LOG.parent.mkdir(parents=True, exist_ok=True)
        if DIAG_LOG.exists():
            DIAG_LOG.unlink()
    except Exception:
        pass

    candidates = []
    env_url = os.environ.get("RIPEN_HUB_URL")
    if env_url:
        candidates.append(env_url)
    if team_url and team_url not in candidates:
        candidates.append(team_url)
    
    local_url = "http://localhost:8377"
    if local_url not in candidates:
        candidates.append(local_url)

    _diag(f"Starting Adaptive Discovery. Candidates: {candidates}")
    
    for hub_url in candidates:
        _diag(f"Attempting to connect to Hub: {hub_url}...")
        try:
            async with sse_client(f"{hub_url.rstrip('/')}/sse") as (read_stream, write_stream):
                _diag(f"SUCCESS: Connected to Hub: {hub_url}")
                
                async def forward_from_hub_to_stdio():
                    """Read from Hub SSE stream, write to stdout."""
                    try:
                        _diag("HUB->STDIO: Starting stream listener...")
                        async for message in read_stream:
                            if isinstance(message, Exception):
                                _diag(f"HUB->STDIO: Stream error (exception): {type(message).__name__}: {message}")
                                continue
                            
                            try:
                                out_json = message.message.model_dump_json(by_alias=True, exclude_none=True)
                                _diag(f"HUB->STDIO: Forwarding full message: {out_json}")
                                # Use binary stdout to avoid Windows CRLF translation issues
                                sys.stdout.buffer.write(out_json.encode("utf-8") + b"\n")
                                sys.stdout.buffer.flush()
                            except Exception as inner_e:
                                _diag(f"HUB->STDIO: Serialization error: {inner_e}")
                    except Exception as e:
                        import traceback
                        _diag(f"HUB->STDIO: Fatal bridge error: {type(e).__name__}: {e}\n{traceback.format_exc()}")

                async def forward_from_stdio_to_hub():
                    """Read from stdin, forward to Hub via SSE write stream."""
                    try:
                        _diag("STDIO->HUB: Waiting for input on stdin...")
                        while True:
                            line = await asyncio.get_event_loop().run_in_executor(
                                None, sys.stdin.readline
                            )
                            if not line:
                                _diag("STDIO->HUB: stdin closed (EOF)")
                                break
                            
                            _diag(f"STDIO->HUB: Received line: {line.strip()[:200]}")
                            
                            try:
                                data = json.loads(line)
                                msg_obj = JSONRPCMessage.model_validate(data)
                                session_msg = SessionMessage(message=msg_obj)
                                await write_stream.send(session_msg)
                                _diag(f"STDIO->HUB: Forwarded successfully (method={data.get('method', 'N/A')})")
                            except json.JSONDecodeError:
                                _diag(f"STDIO->HUB: Invalid JSON: {line.strip()[:100]}")
                            except Exception as e:
                                _diag(f"STDIO->HUB: Forward error: {e}")
                    except Exception as e:
                        _diag(f"Stdio-to-Hub bridge FAILED: {e}")

                await asyncio.gather(
                    forward_from_hub_to_stdio(),
                    forward_from_stdio_to_hub()
                )
                _diag(f"Connection to {hub_url} closed naturally.")
                return 

        except Exception as e:
            _diag(f"Connection FAILED for {hub_url}: {type(e).__name__}: {e}")
            continue

    _diag("FATAL: All Hub candidates exhausted.")
    sys.exit(1)
