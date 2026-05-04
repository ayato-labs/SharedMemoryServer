import asyncio
import json
import os
import sys
import time
from typing import Any

import mcp.shared.session as mcp_session
from mcp.server.fastmcp import FastMCP
from mcp.server.session import InitializationState, ServerSession
from mcp.server.sse import SseServerTransport
from mcp.shared.message import SessionMessage
from mcp.types import (
    INVALID_PARAMS,
    ErrorData,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCNotification,
    JSONRPCRequest,
)
from starlette.applications import Starlette

from shared_memory.common import tasks as tasks_module
from shared_memory.common.utils import configure_logging, get_logger

# --- EXTREME GUARD: STDOUT REDIRECTION ---
# Force all OS-level stdout to stderr to prevent breaking the MCP pipe
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

configure_logging()
logger = get_logger("server")

logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")

# Import core modules with verified paths
logger.info("Importing core submodules...")
try:
    from shared_memory.core import (
        graph as graph_module,
        logic as logic_module,
        thought_logic as thought_module,
    )
    from shared_memory.infra.database import init_db
    logger.info("Core submodules imported successfully")
except Exception:
    logger.exception("Import failure")
    sys.exit(1)

# --- MCP PROTOCOL PATCH: PERMISSIVE HANDSHAKE ---

_original_received_request = ServerSession._received_request

async def _permissive_received_request(self, responder):
    """Wait for initialization, or FORCE it if it takes too long."""
    try:
        request_type = type(responder.request.root.params).__name__
    except Exception:
        request_type = "UnknownRequest"
        
    logger.info(f"[MCP SESSION][{id(self)}] Received {request_type}")
    
    if "InitializeRequest" in request_type:
        return await _original_received_request(self, responder)
    
    # Wait for InitializeRequest to be processed
    retries = 0
    while self._initialization_state in (
        InitializationState.NotInitialized,
        InitializationState.Initializing,
    ):
        if retries >= 40:  # 2.0 seconds
            logger.warning(
                f"[MCP SESSION][{id(self)}] TIMEOUT waiting for initialization. "
                "FORCING INITIALIZED state."
            )
            self._initialization_state = InitializationState.Initialized
            break
        await asyncio.sleep(0.05)
        retries += 1
        
    return await _original_received_request(self, responder)

ServerSession._received_request = _permissive_received_request
logger.info("MCP Protocol Patch: ServerSession._received_request is now PERMISSIVE.")

# --- MCP SDK DEEP PATCH: PERMISSIVE VALIDATION & LOGGING ---

def _sanitize_mcp_dict(d: Any) -> Any:
    if isinstance(d, dict):
        new_d = {}
        for k, v in d.items():
            if isinstance(k, str) and "/" in k:
                continue
            new_d[k] = _sanitize_mcp_dict(v)
        return new_d
    elif isinstance(d, list):
        return [_sanitize_mcp_dict(x) for x in d]
    return d

async def _permissive_session_receive_loop(self):
    import anyio
    from mcp.shared.session import RequestResponder
    
    log_path = "scratch/protocol_log.jsonl"
    os.makedirs("scratch", exist_ok=True)
    
    async with (self._read_stream, self._write_stream):
        try:
            async for message in self._read_stream:
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        log_entry = {
                            "timestamp": time.time(),
                            "session_id": id(self),
                            "type": (
                                type(message.message.root).__name__ 
                                if not isinstance(message, Exception) 
                                else "Exception"
                            ),
                        }
                        if not isinstance(message, Exception):
                            log_entry["content"] = message.message.root.model_dump(mode="json")
                        f.write(json.dumps(log_entry) + "\n")
                except Exception as e:
                    logger.debug(f"Protocol logging failed: {e}")

                if isinstance(message, Exception):
                    await self._handle_incoming(message)
                elif isinstance(message.message.root, JSONRPCRequest):
                    try:
                        raw_dict = message.message.root.model_dump(
                            by_alias=True, mode="json", exclude_none=True
                        )
                        sanitized_dict = _sanitize_mcp_dict(raw_dict)
                        validated_request = self._receive_request_type.model_validate(
                            sanitized_dict
                        )
                        
                        responder = RequestResponder(
                            request_id=message.message.root.id,
                            request_meta=(
                                validated_request.root.params.meta
                                if validated_request.root.params
                                else None
                            ),
                            request=validated_request,
                            session=self,
                            on_complete=lambda r: self._in_flight.pop(r.request_id, None),
                            message_metadata=message.metadata,
                        )
                        self._in_flight[responder.request_id] = responder
                        await self._received_request(responder)
                        if not responder._completed:
                            await self._handle_incoming(responder)
                    except Exception as e:
                        logger.warning(f"[MCP PATCH] Validation failed: {e}")
                        error_response = JSONRPCError(
                            jsonrpc="2.0",
                            id=message.message.root.id,
                            error=ErrorData(
                                code=INVALID_PARAMS,
                                message=f"Invalid request parameters: {e}",
                                data="",
                            ),
                        )
                        await self._write_stream.send(
                            SessionMessage(message=JSONRPCMessage(error_response))
                        )
                elif isinstance(message.message.root, JSONRPCNotification):
                    try:
                        raw_dict = message.message.root.model_dump(
                            by_alias=True, mode="json", exclude_none=True
                        )
                        sanitized_dict = _sanitize_mcp_dict(raw_dict)
                        notification = self._receive_notification_type.model_validate(
                            sanitized_dict
                        )
                        await self._received_notification(notification)
                        await self._handle_incoming(notification)
                    except Exception as e:
                        logger.warning(f"[MCP PATCH] Notification validation failed: {e}")
                else:
                    await self._handle_response(message)
        except anyio.ClosedResourceError:
            pass
        except Exception:
            logger.exception("[MCP PATCH] Unhandled exception")

mcp_session.BaseSession._receive_loop = _permissive_session_receive_loop

# --- FastMCP Patch ---

_original_sse_app = FastMCP.sse_app

def _patched_sse_app(self, mount_path: str | None = None) -> Starlette:
    app = _original_sse_app(self, mount_path)
    return app

FastMCP.sse_app = _patched_sse_app

# Patch SseServerTransport to log POST messages

_original_handle_post = SseServerTransport.handle_post_message

async def _patched_handle_post(self, scope, receive, send):
    query_string = scope.get("query_string", b"").decode()
    session_id = None
    if "session_id=" in query_string:
        import re
        match = re.search(r"session_id=([^&]+)", query_string)
        if match:
            session_id = match.group(1)
            
    logger.info(f"[SSE POST] Received request for session_id={session_id}")
    return await _original_handle_post(self, scope, receive, send)

SseServerTransport.handle_post_message = _patched_handle_post

# --- INITIALIZATION GUARD ---
_INIT_STARTED = False
_INITIALIZED_EVENT = None
_INIT_ERROR = None
_INIT_LOCK = None # Lazy init to avoid loop issues

async def _background_init():
    """Internal initialization logic."""
    global _INITIALIZED_EVENT, _INIT_ERROR
    
    # Reset state if needed for re-initialization (mostly for tests)
    _INIT_ERROR = None
    if not _INITIALIZED_EVENT:
        _INITIALIZED_EVENT = asyncio.Event()
    else:
        _INITIALIZED_EVENT.clear()
        
    try:
        logger.info("Initializing databases...")
        await init_db()
        await thought_module.init_thoughts_db()
        logger.info("Initialization successful.")
        _INITIALIZED_EVENT.set()
    except Exception as e:
        _INIT_ERROR = str(e)
        logger.error(f"[FATAL ERROR] Initialization failed: {e}")
        if _INITIALIZED_EVENT:
            _INITIALIZED_EVENT.set() # Unblock waiters

async def ensure_initialized():
    """Guard for tool execution."""
    global _INIT_STARTED, _INITIALIZED_EVENT, _INIT_LOCK
    
    if _INITIALIZED_EVENT and _INITIALIZED_EVENT.is_set() and not _INIT_ERROR:
        return
        
    if _INIT_ERROR:
        raise RuntimeError(f"Server failed to initialize: {_INIT_ERROR}")

    if _INIT_LOCK is None:
        _INIT_LOCK = asyncio.Lock()

    async with _INIT_LOCK:
        if _INIT_STARTED:
            if not _INITIALIZED_EVENT:
                _INITIALIZED_EVENT = asyncio.Event()
            await _INITIALIZED_EVENT.wait()
            if _INIT_ERROR:
                raise RuntimeError(f"Server failed to initialize: {_INIT_ERROR}")
            return
            
        _INIT_STARTED = True
        await _background_init()

# --- Server Setup ---
mcp = FastMCP("SharedMemoryServer")

@mcp.tool()
async def save_memory(
    agent_id: str = "default_agent",
    entities: list[dict[str, Any]] | list[str] = None,
    observations: list[str] | list[dict[str, Any]] = None,
    relations: list[dict[str, Any]] = None,
    bank_files: dict[str, str] = None,
) -> str:
    """Saves knowledge into both Graph and Bank (Asynchronously)."""
    await ensure_initialized()
    
    # Normalize inputs for background task
    safe_entities = entities or []
    safe_observations = observations or []
    safe_relations = relations or []
    safe_bank_files = bank_files or {}
    
    # Create background task for processing
    tasks_module.create_background_task(
        logic_module.save_memory_core(
            entities=safe_entities,
            observations=safe_observations,
            relations=safe_relations,
            bank_files=safe_bank_files,
            agent_id=agent_id,
        ),
        name=f"save_memory_{int(time.time())}"
    )
    
    targets = []
    if safe_entities:
        targets.append(f"{len(safe_entities)} entities")
    if safe_observations:
        targets.append(f"{len(safe_observations)} observations")
    if safe_bank_files:
        targets.append(f"{len(safe_bank_files)} bank files")
    
    target_str = ", ".join(targets) if targets else "nothing"
    return f"Saved (initiated in background) for: {target_str}."

@mcp.tool()
async def read_memory(query: str) -> str:
    """Reads knowledge from Graph and Bank."""
    await ensure_initialized()
    return await logic_module.read_memory_core(query)

@mcp.tool()
async def manage_knowledge_activation(ids: list[str] | str, status: str) -> str:
    """Enables or disables specific knowledge items."""
    await ensure_initialized()
    
    # Lenient parsing for single ID
    target_ids = [ids] if isinstance(ids, str) else ids
    
    return await logic_module.manage_knowledge_activation_core(target_ids, status)

@mcp.tool()
async def synthesize_entity(entity_name: str) -> str:
    """Triggers an in-depth distillation of a specific entity."""
    await ensure_initialized()
    return await logic_module.synthesize_entity_core(entity_name)

@mcp.tool()
async def get_graph_data(query: str = None) -> str:
    """Retrieves the raw graph structure."""
    await ensure_initialized()
    results = await graph_module.get_graph_data(query)
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def list_inactive_knowledge() -> str:
    """Lists all knowledge items that are currently marked as inactive."""
    await ensure_initialized()
    results = await logic_module.list_inactive_knowledge_core()
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def sequential_thinking(
    thought: str,
    thought_number: int | str,
    total_thoughts: int | str,
    next_thought_needed: bool | str,
    session_id: str = "default_session",
    revises_thought: int | str = None,
    branch_from_thought: int | str = None,
    branch_id: str = None,
    is_revision: bool | str = False,
) -> str:
    """A specialized tool for complex reasoning."""
    await ensure_initialized()
    
    # Lenient parsing for numeric values sent as strings
    def _to_int(val: Any) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _to_bool(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    safe_thought_number = _to_int(thought_number) or 1
    safe_total_thoughts = _to_int(total_thoughts) or 1
    safe_next_thought_needed = _to_bool(next_thought_needed)
    safe_revises_thought = _to_int(revises_thought)
    safe_branch_from_thought = _to_int(branch_from_thought)
    safe_is_revision = _to_bool(is_revision)

    # Note: Using process_thought_core positionally to satisfy tests that check .args
    return await thought_module.process_thought_core(
        thought,
        safe_thought_number,
        safe_total_thoughts,
        safe_next_thought_needed,
        safe_is_revision,
        safe_revises_thought,
        safe_branch_from_thought,
        branch_id,
        session_id
    )

@mcp.tool()
async def get_insights(format: str = "markdown") -> str:
    """Generates a value report based on stored knowledge."""
    await ensure_initialized()
    return await logic_module.get_value_report_core(format)

@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False) -> str:
    """Runs knowledge garbage collection."""
    await ensure_initialized()
    return await logic_module.admin_run_knowledge_gc_core(age_days, dry_run)

def _kill_port_process(port: int):
    try:
        import subprocess
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode()
        for line in output.strip().split('\n'):
            if 'LISTENING' in line:
                pid = line.strip().split()[-1]
                logger.warning(f"Killing zombie process {pid} on port {port}")
                subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
    except Exception as e:
        logger.error(f"Failed to kill zombie process on port {port}: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sse", action="store_true")
    parser.add_argument("--port", type=int, default=8377)
    args = parser.parse_args()
    if args.sse:
        _kill_port_process(args.port)
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")

async def wait_for_background_tasks(timeout: float = 5.0):
    """Waits for background tasks."""
    from shared_memory.common.tasks import wait_for_background_tasks as wait_bg
    await wait_bg(timeout=timeout)

if __name__ == "__main__":
    main()
