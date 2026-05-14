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

# Import project modules
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
logger = get_logger("server")

def get_current_user() -> str:
    return "ayato-labs"

@asynccontextmanager
async def lifespan(mcp_instance: FastMCP) -> AsyncGenerator[None, None]:
    """MCP Server lifespan handler for DB and system initialization."""
    logger.info("Ripen Hub: Starting lifespan sequence...")
    
    # 1. Initialize Database
    await init_db()
    
    # 2. Initialize Thoughts Logic
    await thought_module.init_thoughts_db()
    
    # 3. Verify LLM Connectivity
    try:
        provider = get_llm_provider()
        logger.debug(f"LLM Provider: {provider}")
        logger.info("[BACKEND STATUS] AI Brain (LLM): OK")
    except Exception as e:
        logger.error(f"AI Brain connectivity failed: {e}")
        # We don't crash here, as some tools might work without LLM
        
    # 4. Start Background Tasks
    create_background_task(start_database_maintenance())
    
    logger.info("Ripen Hub: Startup complete.")
    yield
    logger.info("Ripen Hub: Shutting down...")

# Create FastMCP server instance
mcp = FastMCP(
    "Ripen-v2",
    version="3.2.4",
)

# --- DASHBOARD MOUNT ---
try:
    from ripen.api.dashboard import router as dashboard_router
    mcp.app.mount("/dashboard", dashboard_router)
    logger.info("Dashboard mounted at /dashboard")
except Exception as e:
    logger.warning(f"Failed to mount dashboard: {e}")

# --- MCP TOOLS ---

@mcp.tool()
async def save_memory(
    entities: list[dict],
    relations: list[dict],
    observations: list[dict],
    bank_files: list[str] | None = None,
    agent_id: str | None = None,
) -> str:
    """
    Persists knowledge to the long-term memory hub.
    Input should follow the structured JSON format for entities and relations.
    """
    logger.info(f"Tool called: save_memory (Entities: {len(entities)}, Relations: {len(relations)})")
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

# --- ENTRY POINT ---

def print_banner(mode: str, port: int):
    lm = LicenseManager()
    lm.validate_locally()
    license_text = lm.get_status_summary()

    print("\033[1;32m" + "=" * 60 + "\033[0m", file=sys.stderr)
    print("  Ripen Knowledge Hub v3.2.4", file=sys.stderr)
    print("  \033[1;30m" + "" + "\033[0m", file=sys.stderr)
    print(f"  Mode:      {mode}", file=sys.stderr)
    print(f"  Port:      {port}", file=sys.stderr)
    print(
        f"  LLM:       {settings.llm_provider} ({settings.generative_model})", file=sys.stderr
    )
    print(f"  Data:      {settings.base_dir}", file=sys.stderr)
    print(f"  Dashboard: http://localhost:{port}/dashboard", file=sys.stderr)
    print(f"  License:   {license_text}", file=sys.stderr)
    print("\033[1;32m" + "=" * 60 + "\033[0m", file=sys.stderr)
    print(file=sys.stderr)

def main():
    configure_logging()
    logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")

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

    parser = argparse.ArgumentParser(description="Ripen Hub Server")
    parser.add_argument("--stdio", action="store_true", help="Start in STDIO proxy mode")
    parser.add_argument("--sse", action="store_true", help="Start in SSE mode (HTTP)")
    parser.add_argument("--port", type=int, help="Port for SSE mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE mode")
    parser.add_argument("--dev", action="store_true", help="Start in development mode")
    parser.add_argument("--hub-url", dest="hub_url", help="Hub URL (for Proxy mode)")
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
        PluginLoader.load_all(context={"settings": settings})
        print_banner("SSE (Server-Sent Events)", port)
        mcp.run(transport="sse", host=args.host, port=port)
    else:
        # STDIO mode: Check if we should run as a proxy or native server
        target_hub = args.hub_url or args.hub_url_pos
        if target_hub and "<" not in target_hub:
            logger.info(f"Starting STDIO Proxy -> {target_hub}")
            asyncio.run(run_stdio_proxy(target_hub))
        else:
            # Native STDIO mode
            PluginLoader.load_all(context={"settings": settings})
            print_banner("STDIO (Standard I/O)", 0)
            mcp.run(transport="stdio", show_banner=False)

if __name__ == "__main__":
    safe_main_executor(main)()
