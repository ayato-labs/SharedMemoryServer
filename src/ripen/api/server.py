import argparse
import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

# Force prioritize local src to ensure Hub and Proxy use the same latest code
CURRENT_SRC = str(Path(__file__).parent.parent.parent.absolute())
if CURRENT_SRC not in sys.path:
    sys.path.insert(0, CURRENT_SRC)

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

from ripen.api.dashboard import router as dashboard_router
from ripen.api.licensing import LicenseManager
from ripen.common.config import settings
from ripen.common.plugins import PluginLoader
from ripen.common.tasks import create_background_task, wait_for_background_tasks as _wait_tasks
from ripen.common.utils import configure_logging, get_logger, safe_main_executor
from ripen.infra.database import init_db
from ripen.infra.llm import get_llm_provider
from ripen.ops.lifecycle import start_database_maintenance


async def ensure_initialized():
    """Legacy helper for tests and external scripts."""
    await init_db()
    await thought_module.init_thoughts_db()

# Import core modules
from ripen.core import (
    graph as graph_module,
    logic as logic_module,
    thought_logic as thought_module,
)

# --- INITIALIZATION ---
logger = get_logger("server")

def get_current_user() -> str:
    return "ayato-labs"

# Create FastMCP server instance
# Using Ripen-v2 and version from main branch as it seems to be the target release version
mcp = FastMCP(
    "Ripen-v2",
    version="3.2.4",
)

# Attach Dashboard
# Note: FastMCP.mount() is for mounting other FastMCP servers.
# To mount a Starlette Router, we add it to _additional_http_routes.
mcp._additional_http_routes.append(Mount("/dashboard", app=dashboard_router))

def handle_exception(_loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"ASYNC_LOOP_CRITICAL: {msg}")
    import traceback
    if "exception" in context:
        logger.error("".join(traceback.format_exception(context["exception"])))

@asynccontextmanager
async def lifespan(_app: Starlette) -> AsyncGenerator[None, None]:
    """Startup sequence for the hub."""
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_exception)
    
    logger.info("Ripen Hub: Starting lifespan sequence...")

    # 1. Init Database
    await init_db()

    # 2. Init Thoughts DB
    await thought_module.init_thoughts_db()

    # 3. Start Maintenance Tasks
    maintenance_task = create_background_task(start_database_maintenance())

    # 4. Check AI Provider
    try:
        provider = get_llm_provider()
        if await provider.check_health():
            logger.info("[BACKEND STATUS] AI Brain (LLM): OK")
        else:
            logger.warning("[BACKEND STATUS] AI Brain (LLM): NOT CONFIGURED")
    except Exception as e:
        logger.error(f"[BACKEND STATUS] AI Brain (LLM): FAILED - {e}")

    logger.info("Ripen Hub: Startup complete. Listening for connections.")
    
    try:
        yield
    finally:
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass

mcp._lifespan = lifespan

# --- TOOLS ---

@mcp.tool()
async def save_memory(
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
    observations: list[str] | None = None,
    bank_files: list[dict] | None = None,
    agent_id: str | None = None,
) -> str:
    """
    Persists new knowledge into the memory hub.
    - entities: List of {name, type, description}
    - relations: List of {source, target, relation_type}
    - observations: List of factual strings
    - bank_files: List of {path, content} for technical references
    """
    logger.info(f"Tool called: save_memory by agent='{agent_id}'")
    user = agent_id or get_current_user() or "default_agent"
    try:
        await logic_module.save_memory_core(
            entities=entities,
            relations=relations,
            observations=observations,
            bank_files=bank_files,
            agent_id=user,
        )
        return "Knowledge successfully persisted to the hub."
    except Exception as e:
        logger.exception("Failed to save memory")
        return f"Error: {e}"

@mcp.tool()
async def read_memory(query: str = "") -> str:
    """
    Retrieves relevant knowledge from the memory hub using hybrid search.
    Use this to gather context about entities, relations, and past observations.
    """
    logger.info(f"Tool called: read_memory(query='{query}')")
    results = await logic_module.read_memory_core(query)
    if not results:
        return "No relevant memories found."
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    session_id: str | None = None,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    is_revision: bool = False,
) -> str:
    """
    A tool for complex reasoning. Allows the agent to iterate through thoughts,
    branch ideas, and maintain a structured thinking process.
    """
    logger.info(f"Tool called: sequential_thinking (Thought {thought_number}/{total_thoughts})")
    user = get_current_user() or "default_agent"
    try:
        result = await thought_module.process_thought_core(
            thought=thought,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            next_thought_needed=next_thought_needed,
            session_id=session_id,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            is_revision=is_revision,
            agent_id=user
        )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.exception("Sequential thinking failed")
        return f"Thinking Error: {e}"

@mcp.tool()
async def synthesize_entity(entity_name: str) -> str:
    """Generate a synthesized summary of an entity based on all known observations and relations."""
    summary = await logic_module.synthesize_entity(entity_name)
    return json.dumps(summary, indent=2, ensure_ascii=False)

@mcp.tool()
async def save_troubleshooting_knowledge(
    title: str,
    solution: str,
    affected_functions: list[str] | None = None,
    env_metadata: dict | None = None,
) -> str:
    """Save troubleshooting knowledge to help future agents solve similar issues."""
    return await logic_module.save_troubleshooting_knowledge_core(
        title, solution, affected_functions, env_metadata
    )

@mcp.tool()
async def get_graph_data(_query: str | None = None) -> str:
    """Retrieve raw graph data (nodes and edges) for visualization or deep analysis."""
    data = await graph_module.get_graph_data()
    return json.dumps(data, indent=2, ensure_ascii=False)

@mcp.tool()
async def manage_knowledge_activation(ids: list[str] | str, status: str) -> str:
    """Govern the 'Maturity' and 'Activation' of knowledge.
    Use this to manually activate important patterns or archive transient noise."""
    await logic_module.manage_knowledge_activation_core(ids, status)
    return f"Status updated to {status}."

@mcp.tool()
async def list_inactive_knowledge() -> list[dict]:
    """List archived or low-maturity knowledge.
    Use this to review what has been filtered out and identify if any critical
    information needs to be 're-activated'."""
    return await logic_module.list_inactive_knowledge_core()

@mcp.tool()
async def get_insights(format: str = "markdown") -> str:
    """Generate a high-level value report and ROI of the memory system."""
    return await logic_module.get_value_report_core(format_type=format)

@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False) -> str:
    """System maintenance: Garbage collection.
    Trigger this to purge ancient, unused knowledge and maintain system performance."""
    return await logic_module.admin_run_knowledge_gc_core(age_days, dry_run)

# --- MCP PROTOCOL PATCH (DEEP TRACING) ---
try:
    from mcp.server.session import InitializationState, ServerSession
    _orig_received_request = ServerSession._received_request

    async def _patched_received_request(self, responder):
        """
        Modified MCP Protocol handler with Permissive Handshake support.
        Automatically handles out-of-order requests and downgrades log alarms.
        """
        try:
            # --- Permissive Handshake Logic ---
            # Handle states where the SDK would normally reject requests
            if self._initialization_state in (
                InitializationState.NotInitialized,
                InitializationState.Initializing,
            ):
                from mcp.types import InitializeRequest, PingRequest
                req_root = responder.request.root
                if not isinstance(req_root, (InitializeRequest, PingRequest)):
                    # Force transition to Initialized to prevent RuntimeError in underlying SDK
                    state_name = self._initialization_state.name
                    logger.warning(
                        f"Permissive Handshake: Auto-initializing session from "
                        f"'{state_name}' for {type(req_root).__name__}"
                    )
                    self._initialization_state = InitializationState.Initialized

            # Trace request
            req_repr = repr(responder.request)
            logger.debug(f"MCP_REQ_TRACE: {req_repr}")

            return await _orig_received_request(self, responder)

        except RuntimeError as e:
            # Handle standard protocol state errors as warnings
            if "before initialization was complete" in str(e):
                logger.warning(f"MCP Protocol State Warning: {e}")
                return # Suppress critical alarm
            raise
        except Exception as e:
            # Log true crashes as CRITICAL
            logger.error(f"MCP Protocol CRITICAL: Failed to process request: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    ServerSession._received_request = _patched_received_request
    logger.info("MCP Protocol Patch: Deep Tracing & Permissive Handshake enabled.")
except Exception as e:
    logger.warning(f"Failed to apply MCP Protocol Patch: {e}")
# --- ENTRY POINT ---


def print_banner(mode: str, port: int):
    lm = LicenseManager()
    lm.validate_locally()
    license_text = lm.get_status_summary()

    lines = [
        "\033[1;32m" + "=" * 60 + "\033[0m",
        "  Ripen Knowledge Hub v3.2.4",
        "  \033[1;30m" + "" + "\033[0m",
        f"  \033[1;34m[Mode]\033[0m      {mode}",
        f"  \033[1;32m[Port]\033[0m      {port}",
        f"  \033[1;33m[LLM]\033[0m       {settings.llm_provider} ({settings.generative_model})",
        f"  \033[1;36m[Data]\033[0m      {settings.base_dir}",
        f"  \033[1;35m[Dashboard]\033[0m http://localhost:{port}/dashboard",
        f"  \033[1;37m[License]\033[0m   {license_text}",
        "\033[1;32m" + "=" * 60 + "\033[0m",
        ""
    ]
    
    for line in lines:
        try:
            sys.stderr.write(line + "\n")
        except UnicodeEncodeError:
            # Fallback for strict terminals
            sys.stderr.write(line.encode('ascii', 'ignore').decode('ascii') + "\n")
    sys.stderr.flush()

def main():
    configure_logging()
    logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")
    logger.info(f"Main execution started (Args: {sys.argv})")


    parser = argparse.ArgumentParser(description="Ripen Hub Server")
    parser.add_argument("--port", type=int, help="Port for the server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for the server")
    parser.add_argument("--dev", action="store_true", help="Start in development mode")

    args = parser.parse_args()
    logger.debug("Arguments parsed successfully.")

    if args.dev:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Handle termination signals
    def handle_signal(sig, _frame):
        logger.info(f"Signal {sig} received. Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    port = args.port or settings.sse_port or 8377
    logger.info(f"Port check: port={port}")

    logger.info("Starting cleanup and port check...")
    _kill_port_process(port)
    logger.info("Cleanup completed. Checking port availability...")

    # Double check port availability
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", port))
    if result == 0:
        logger.error(
            f"PORT CONFLICT: Port {port} is already in use by another process. "
            f"Please stop all other Ripen Hub instances."
        )
        sock.close()
        sys.exit(1)
    sock.close()
    logger.info("Port is available.")

    # Load plugins before starting
    logger.info("Loading plugins...")
    PluginLoader.load_all(context={"settings": settings})
    logger.info("Plugins loaded. Printing banner...")
    print_banner("Streamable HTTP", port)
    logger.info("Banner printed. Running FastMCP server...")
    mcp.run(transport="streamable-http", host=args.host, port=port, show_banner=False)


def _kill_port_process(port: int):
    """
    Attempts to kill any process listening on the specified port.
    This is a stability fix for Windows where zombie processes can hold ports.
    """
    if sys.platform != "win32":
        return

    current_pid = os.getpid()
    logger.info(f"Executing _kill_port_process for port {port} (Current PID: {current_pid})")
    try:
        import subprocess
        # 1. Kill by port
        cmd = f"netstat -ano | findstr :{port}"
        logger.debug(f"Running: {cmd}")
        try:
            output = subprocess.check_output(cmd, shell=True).decode()
            logger.debug(f"netstat output: {output}")
            for line in output.strip().split("\n"):
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        try:
                            pid_int = int(pid)
                            if pid_int not in (0, current_pid):
                                logger.warning(f"Killing zombie process {pid_int} on port {port}")
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(pid_int)],
                                    check=False,
                                    capture_output=True,
                                )
                        except ValueError:
                            logger.warning(f"Could not parse PID from line: {line}")
        except subprocess.CalledProcessError:
            logger.debug("No process found listening on port.")

        # 2. Kill by name (Aggressive Cleanup)
        # This ensures no duplicate proxies or hubs are hanging around
        # We MUST exclude our own PID to avoid self-termination
        logger.debug("Performing aggressive cleanup...")
        # Note: taskkill /IM kills by process name. If the current process is
        # ripen.exe, this would kill it.
        # We use /FI to exclude the current PID.
        subprocess.run(
            f'taskkill /F /IM ripen.exe /FI "PID ne {current_pid}"',
            shell=True,
            check=False,
            capture_output=True,
        )
        
        # We removed the WMIC-based cleanup because its command line often matched 
        # the filter pattern, causing the shell to terminate prematurely.
        # The netstat check above is sufficient for port conflicts.
            
    except Exception as e:
        logger.error(f"Aggressive cleanup failed: {e}")


async def wait_for_background_tasks(timeout: float = 5.0):
    """
    Waits for all registered background tasks to complete or timeout.
    """
    await _wait_tasks(timeout=timeout)

if __name__ == "__main__":
    safe_main_executor(main)()
