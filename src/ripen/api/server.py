import asyncio
import json
import re
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from mcp.server.session import InitializationState, ServerSession
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette

from ripen.api.auth import AuthMiddleware, get_current_user
from ripen.common.config import settings
from ripen.common.tasks import create_background_task
from ripen.common.utils import configure_logging, get_logger
from ripen.ops.lifecycle import start_database_maintenance

# --- EXTREME GUARD: STDOUT REDIRECTION ---
# Force all OS-level stdout to stderr to prevent breaking the MCP pipe
sys.stdout = sys.stderr

configure_logging()
logger = get_logger("server")

logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")

# Import core modules with verified paths
logger.info("Importing core submodules...")
try:
    from ripen.api.dashboard import router as dashboard_router
    from ripen.core import (
        graph as graph_module,
        logic as logic_module,
        thought_logic as thought_module,
    )
    from ripen.infra.database import init_db

    logger.info("Core submodules and Dashboard router imported successfully")
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
    """Recursively converts all string numbers to actual numbers for MCP validation."""
    if isinstance(d, dict):
        return {k: _sanitize_mcp_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [_sanitize_mcp_dict(v) for v in d]
    elif isinstance(d, str):
        try:
            if "." in d:
                return float(d)
            return int(d)
        except (ValueError, TypeError):
            return d
    return d


# Patch FastMCP session handling to be more resilient to string/number mismatches
_original_http_app = FastMCP.http_app


def _patched_http_app(self, *args, **kwargs) -> Starlette:
    # Use the original http_app but we want to mount our Dashboard and Auth
    app = _original_http_app(self, *args, **kwargs)
    logger.info("Current middleware stack in Starlette app:")
    for i, m in enumerate(app.user_middleware):
        logger.info(f" Middleware {i}: {m.cls} (Bases: {getattr(m.cls, '__bases__', 'N/A')})")

    app.add_middleware(AuthMiddleware)
    # Mount Dashboard routes
    app.mount("/dashboard", dashboard_router)
    return app


FastMCP.http_app = _patched_http_app

_original_handle_post = SseServerTransport.handle_post_message


async def _patched_handle_post(self, scope, receive, send):
    # We can peek at the scope for query params without consuming the body
    query_string = scope.get("query_string", b"").decode()
    session_id = None
    if "session_id=" in query_string:
        match = re.search(r"session_id=([^&]+)", query_string)
        if match:
            session_id = match.group(1)

    logger.info(f"[SSE POST] Received request for session_id={session_id}")
    if not session_id:
        logger.warning("[SSE POST] REJECTED: Missing session_id")

    return await _original_handle_post(self, scope, receive, send)


SseServerTransport.handle_post_message = _patched_handle_post


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Ensure database is ready and start background maintenance."""
    await init_db()
    # Start periodic database maintenance (PRAGMA optimize)
    create_background_task(start_database_maintenance(), name="db_maintenance")
    yield


# --- Server Setup ---
mcp = FastMCP(
    "Ripen",
    instructions=(
        "A production-grade long-term memory server for AI agents. "
        "Provides semantic search, graph-based knowledge retrieval, "
        "and persistent reasoning provenance."
    ),
    lifespan=lifespan,
)




@mcp.tool(
    description=(
        "The gateway to your long-term memory. Use this to persist high-signal information, "
        "verified architectural decisions, and stable domain knowledge. "
        "Focus on structured 'entities' and 'relations' to build a "
        "permanent 'Single Source of Truth'."
    )
)
async def save_memory(
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
    observations: list[dict] | None = None,
    bank_files: dict | None = None,
    agent_id: str | None = None,
) -> str:
    """The gateway to your long-term memory."""

    user = agent_id or get_current_user() or "default_agent"
    return await logic_module.save_memory_core(entities, relations, observations, bank_files, user)


@mcp.tool(
    description=(
        "A hybrid semantic/full-text search interface to your external hippocampus. "
        "Use this at the beginning of any task to 'salvage' relevant past context "
        "and avoid reinventing the wheel."
    )
)
async def read_memory(query: str | None = None) -> str:
    """A hybrid semantic/full-text search interface to your external hippocampus."""

    results = await logic_module.read_memory_core(query)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool(
    description=(
        "Synthesize all available knowledge about a specific entity into a comprehensive summary. "
        "Use this when 'read_memory' provides an ID or name you need to investigate in depth."
    )
)
async def synthesize_entity(entity_name: str) -> str:
    """Synthesize all available knowledge about a specific entity."""

    summary = await logic_module.synthesize_entity(entity_name)
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool(
    description=(
        "Retrieve the structural relationships (graph) of knowledge. "
        "Use this to understand dependencies, hierarchical connections, "
        "and how different entities relate to each other."
    )
)
async def get_graph_data(query: str | None = None) -> str:
    """Retrieve the structural relationships (graph) of knowledge."""

    data = await graph_module.get_graph_data(query)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool(
    description=(
        "An advanced reasoning tool to externalize and govern your inference process. "
        "Use this as your primary cognitive workspace to break down complex problems."
    )
)
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
    """An advanced reasoning tool to externalize and govern your inference process."""

    user = get_current_user() or "default_agent"
    result = await thought_module.process_thought_core(
        thought=thought,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        next_thought_needed=next_thought_needed,
        session_id=session_id,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id,
        is_revision=is_revision,
        revises_thought=revises_thought,
        agent_id=user,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(
    description=(
        "Govern the 'Maturity' and 'Activation' of knowledge. "
        "Use this to manually activate important patterns or archive transient noise."
    )
)
async def manage_knowledge_activation(ids: Any, status: str) -> str:
    """Govern the 'Maturity' and 'Activation' of knowledge."""

    await logic_module.manage_knowledge_activation_core(ids, status)
    return f"Status updated to {status}."


@mcp.tool(
    description=(
        "List archived or low-maturity knowledge. Use this to review what has been "
        "filtered out and identify if any critical information needs to be 're-activated'."
    )
)
async def list_inactive_knowledge() -> str:
    """List archived or low-maturity knowledge."""

    results = await logic_module.list_inactive_knowledge_core()
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool(
    description="Generate a high-level value report and ROI of the memory system."
)
async def get_insights(format: str = "markdown") -> str:
    """Generate a high-level value report and ROI of the memory system."""

    return await logic_module.get_value_report_core(format)


@mcp.tool(
    description=(
        "System maintenance: Garbage collection. Trigger this to purge ancient, "
        "unused knowledge and maintain system performance."
    )
)
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False) -> str:
    """System maintenance: Garbage collection."""

    return await logic_module.admin_run_knowledge_gc_core(age_days, dry_run)


def _kill_port_process(port: int):
    try:
        import subprocess

        cmd = f"netstat -ano | findstr :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        for line in output.strip().split("\n"):
            if "LISTENING" in line:
                pid = line.strip().split()[-1]
                logger.warning(f"Killing zombie process {pid} on port {port}")
                subprocess.run(["taskkill", "/F", "/PID", pid], check=True)
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
        
        print("\n" + "="*50)
        print(f"\033[1;32m✅ Ripen v0.1.0 is running (SSE Mode)\033[0m")
        print(f"  Transport: \033[1;36mSSE on port {args.port}\033[0m")
        print(f"  LLM:       \033[1;33m{settings.llm_provider} ({settings.generative_model})\033[0m")
        print(f"  Data:      \033[1;34m{settings.base_dir}\033[0m")
        print(f"  Dashboard: \033[1;35mhttp://localhost:{args.port}/dashboard\033[0m")
        print("="*50 + "\n")
        
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")


async def ensure_initialized():
    """
    Explicitly ensures the database and infrastructure are initialized.
    Used primarily by system tests to synchronize state.
    """
    logger.info("Server: Ensuring initialization...")
    await init_db()
    await thought_module.init_thoughts_db()
    logger.info("Server: Initialization complete.")


async def wait_for_background_tasks(timeout: float = 5.0):
    """
    Waits for all background tasks to complete or timeout.
    Used during server shutdown and test teardown.
    """
    from ripen.common.tasks import (
        wait_for_background_tasks as wait_tasks,
    )

    await wait_tasks(timeout=timeout)


if __name__ == "__main__":
    main()
