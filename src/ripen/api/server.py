import argparse
import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastmcp import FastMCP
from loguru import logger
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from ripen.api.auth import dashboard_router
from ripen.api.licensing import LicenseManager
from ripen.common.config import settings
from ripen.common.plugins import PluginLoader
from ripen.common.tasks import create_background_task
from ripen.common.utils import configure_logging, get_logger, safe_main_executor
from ripen.ops.lifecycle import start_database_maintenance
from ripen.infra.database import init_db
from ripen.infra.llm import get_llm_provider
from ripen.api.proxy import run_stdio_proxy
from ripen.ops.hub_manager import ensure_hub_running

# Import core modules
from ripen.core import (
    graph as graph_module,
    logic as logic_module,
    search as search_module,
    thought_logic as thought_module,
)

# --- INITIALIZATION ---
configure_logging()
logger = get_logger("server")
logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")

def get_current_user() -> str:
    return "ayato-labs"

# Create FastMCP server instance
# Using Ripen-v2 and version from main branch as it seems to be the target release version
mcp = FastMCP(
    "Ripen-v2",
    version="3.2.4",
    description="The centralized knowledge hub for AI agents. Hybrid Vector + Graph memory.",
)

# Attach Dashboard
mcp.add_router(dashboard_router, prefix="/dashboard")

@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Startup sequence for the hub."""
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

    logger.info("Ripen Hub: Startup complete.")
    
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
async def get_graph_data(query: str | None = None) -> str:
    """Retrieve raw graph data (nodes and edges) for visualization or deep analysis."""
    data = await graph_module.get_graph_data()
    return json.dumps(data, indent=2, ensure_ascii=False)

@mcp.tool()
async def manage_knowledge_activation(ids: list[str] | str, status: str) -> str:
    """Govern the 'Maturity' and 'Activation' of knowledge. Use this to manually activate important patterns or archive transient noise."""
    await logic_module.manage_knowledge_activation_core(ids, status)
    return f"Status updated to {status}."

@mcp.tool()
async def list_inactive_knowledge() -> str:
    """List archived or low-maturity knowledge. Use this to review what has been filtered out and identify if any critical information needs to be 're-activated'."""
    results = await logic_module.list_inactive_knowledge_core()
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def get_insights(format: str = "markdown") -> str:
    """Generate a high-level value report and ROI of the memory system."""
    return await logic_module.get_value_report_core(format_type=format)

@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False) -> str:
    """System maintenance: Garbage collection. Trigger this to purge ancient, unused knowledge and maintain system performance."""
    return await logic_module.admin_run_knowledge_gc_core(age_days, dry_run)

# --- MCP PROTOCOL PATCH ---
try:
    from mcp.server.session import ServerSession
    _orig_received_request = ServerSession._received_request
    async def _patched_received_request(self, request):
        try:
            return await _orig_received_request(self, request)
        except Exception as e:
            logger.error(f"MCP Protocol Error: Handled malformed request: {e}")
            pass
    ServerSession._received_request = _patched_received_request
    logger.info("MCP Protocol Patch: ServerSession._received_request is now PERMISSIVE.")
except Exception as e:
    logger.warning(f"Failed to apply MCP Protocol Patch: {e}")

# --- ENTRY POINT ---

def print_banner(mode: str, port: int):
    lm = LicenseManager()
    lm.validate_locally()
    license_text = lm.get_status_summary()

    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print("  Ripen Knowledge Hub v3.2.4")
    print("  \033[1;30m" + "" + "\033[0m")
    print(f"  \033[1;34m\U0001f9e0 Mode:\033[0m      {mode}")
    print(f"  \033[1;32m\U0001f4e1 Port:\033[0m      {port}")
    print(
        f"  \033[1;33m\U0001f916 LLM:\033[0m       {settings.llm_provider} ({settings.generative_model})"
    )
    print(f"  \033[1;36m\U0001f4c2 Data:\033[0m      {settings.base_dir}")
    print(f"  \033[1;35m\U0001f4ca Dashboard:\033[0m http://localhost:{port}/dashboard")
    print(f"  \033[1;37m\U0001f4dc License:\033[0m   {license_text}")
    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print()

def main():
    parser = argparse.ArgumentParser(description="Ripen Hub Server")
    parser.add_argument("--stdio", action="store_true", help="Start in STDIO proxy mode")
    parser.add_argument("--sse", action="store_true", help="Start in SSE mode (HTTP)")
    parser.add_argument("--port", type=int, help="Port for SSE mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE mode")
    parser.add_argument("--dev", action="store_true", help="Start in development mode")
    parser.add_argument("hub_url_pos", type=str, nargs="?", help="Hub URL (for Proxy mode)")

    args = parser.parse_args()

    if args.dev:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Handle termination signals
    def handle_signal(sig, frame):
        logger.info(f"Signal {sig} received. Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Determine transport mode
    if args.stdio:
        use_sse = False
    else:
        use_sse = args.sse or settings.default_transport == "sse"

    port = args.port or settings.sse_port or 8377

    if use_sse:
        # Load plugins before starting
        PluginLoader().load_all()
        print_banner("SSE (Server-Sent Events)", port)
        mcp.run(transport="sse", host=args.host, port=port)
    else:
        # STDIO mode: Check if we should run as a proxy or native server
        target_hub = args.hub_url_pos
        if target_hub and "<" not in target_hub:
            logger.info(f"Starting STDIO Proxy -> {target_hub}")
            asyncio.run(run_stdio_proxy(target_hub))
        else:
            # Native STDIO mode
            PluginLoader().load_all()
            print_banner("STDIO (Standard I/O)", 0)
            mcp.run(transport="stdio")

if __name__ == "__main__":
    safe_main_executor(main)()
