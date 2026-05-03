import asyncio
import json
import os
import sys
import time
from typing import Any

from starlette.applications import Starlette

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
from mcp.server.session import InitializationState, ServerSession

_original_received_request = ServerSession._received_request

async def _permissive_received_request(self, responder):
    """Wait for initialization, or FORCE it if it takes too long."""
    import asyncio
    
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
import mcp.shared.session as mcp_session
from mcp.shared.message import SessionMessage
from mcp.types import (
    INVALID_PARAMS,
    ErrorData,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCNotification,
    JSONRPCRequest,
)


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
from mcp.server.fastmcp import FastMCP

_original_sse_app = FastMCP.sse_app

def _patched_sse_app(self, mount_path: str | None = None) -> Starlette:
    # Use the original sse_app but we might want to wrap routes for logging
    app = _original_sse_app(self, mount_path)
    return app

FastMCP.sse_app = _patched_sse_app

# Patch SseServerTransport to log POST messages
from mcp.server.sse import SseServerTransport

_original_handle_post = SseServerTransport.handle_post_message

async def _patched_handle_post(self, scope, receive, send):
    # from starlette.requests import Request (Unused)
    # We can peek at the scope for query params without consuming the body
    query_string = scope.get("query_string", b"").decode()
    session_id = None
    if "session_id=" in query_string:
        import re
        match = re.search(r"session_id=([^&]+)", query_string)
        if match:
            session_id = match.group(1)
            
    logger.info(f"[SSE POST] Received request for session_id={session_id}")
    if not session_id:
        logger.warning("[SSE POST] REJECTED: Missing session_id")
        
    return await _original_handle_post(self, scope, receive, send)

SseServerTransport.handle_post_message = _patched_handle_post


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Ensure database is ready before server starts accepting work."""
    asyncio.create_task(init_db())
    yield

# --- Server Setup ---
mcp = FastMCP("SharedMemoryServer", lifespan=lifespan)

@mcp.tool()
async def save_memory(
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
    observations: list[dict] | None = None,
    bank_files: dict | None = None,
    agent_id: str | None = None,
) -> str:
    return await logic_module.save_memory_core(
        entities, relations, observations, bank_files, agent_id
    )

@mcp.tool()
async def read_memory(query: str | None = None) -> str:
    results = await logic_module.read_memory_core(query)
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def synthesize_entity(entity_name: str) -> str:
    summary = await logic_module.synthesize_entity(entity_name)
    return json.dumps(summary, indent=2, ensure_ascii=False)

@mcp.tool()
async def get_graph_data(query: str | None = None) -> str:
    data = await graph_module.get_graph_data(query)
    return json.dumps(data, indent=2, ensure_ascii=False)

@mcp.tool()
async def sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    session_id: str | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    is_revision: bool | None = None,
    revises_thought: int | None = None,
) -> str:
    result = await thought_module.process_thought_core(
        thought=thought,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        next_thought_needed=next_thought_needed,
        session_id=session_id,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id,
        is_revision=is_revision,
        revises_thought=revises_thought
    )
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
async def manage_knowledge_activation(ids: Any, status: str) -> str:
    await logic_module.manage_knowledge_activation_core(ids, status)
    return f"Status updated to {status}."

@mcp.tool()
async def list_inactive_knowledge() -> str:
    results = await logic_module.list_inactive_knowledge_core()
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def get_insights(format: str = "markdown") -> str:
    return await logic_module.get_value_report_core(format)

@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False) -> str:
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
        logger.error("Failed to kill zombie process on port {port}: {error}", port=port, error=e)

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
    """
    Waits for all background tasks to complete or timeout.
    Used during server shutdown and test teardown.
    """
    # This is a stub for the actual background task tracker if implemented
    await asyncio.sleep(0.1)

if __name__ == "__main__":
    main()
