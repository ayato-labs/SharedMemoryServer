import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from ripen.common.config import settings
from ripen.common.utils import get_logger
from ripen.core import graph as graph_module
from ripen.core import logic as logic_module
from ripen.core import search as search_module
from ripen.core import thought_logic as thought_module
from ripen.ops.lifecycle import start_database_maintenance
from ripen.infra.database import init_db
from ripen.infra.llm import get_llm_provider
from ripen.common.tasks import create_background_task
from ripen.api.proxy import run_stdio_proxy
from ripen.ops.hub_manager import ensure_hub_running

logger = get_logger("server")

def get_current_user() -> str:
    return "ayato-labs"

mcp = FastMCP(
    "Ripen-v2",
    version="3.2.4",
)

@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    # Initialize infrastructure
    await init_db()
    
    # Verify LLM
    try:
        provider = get_llm_provider()
        if await provider.check_health():
            logger.info("[BACKEND STATUS] AI Brain (LLM): OK")
        else:
            logger.warning("[BACKEND STATUS] AI Brain (LLM): NOT CONFIGURED")
    except Exception as e:
        logger.error(f"[BACKEND STATUS] AI Brain (LLM): FAILED - {e}")

    # Start background maintenance
    maintenance_task = create_background_task(start_database_maintenance())
    
    try:
        yield
    finally:
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass

mcp._lifespan = lifespan

# --- Tools ---

@mcp.tool()
async def save_memory(
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
    observations: list[dict] | None = None,
    bank_files: dict | None = None,
    agent_id: str | None = None,
) -> str:
    user = agent_id or get_current_user() or "default_agent"
    return await logic_module.save_memory_core(entities, relations, observations, bank_files, user)

@mcp.tool()
async def read_memory(query: str | None = None) -> str:
    results = await logic_module.read_memory_core(query)
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def synthesize_entity(entity_name: str) -> str:
    summary = await logic_module.synthesize_entity(entity_name)
    return json.dumps(summary, indent=2, ensure_ascii=False)

@mcp.tool()
async def save_troubleshooting_knowledge(
    title: str,
    solution: str,
    affected_functions: list[str] | None = None,
    env_metadata: dict | None = None,
) -> str:
    return await logic_module.save_troubleshooting_knowledge_core(
        title, solution, affected_functions, env_metadata
    )

@mcp.tool()
async def get_graph_data(query: str | None = None) -> str:
    data = await graph_module.get_graph_data()
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

# --- CLI Entry Point ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ripen MCP Server / Proxy")
    parser.add_argument("--stdio", action="store_true", help="Run in STDIO proxy mode")
    parser.add_argument("--sse", action="store_true", help="Run in SSE server mode")
    parser.add_argument("--port", type=int, help="Port for SSE server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for SSE server")
    parser.add_argument("hub_url_pos", type=str, nargs="?", help="Hub URL")
    args = parser.parse_args()

    # Determine transport mode
    if args.stdio:
        use_sse = False
    else:
        use_sse = args.sse or settings.default_transport == "sse"

    port = args.port or settings.sse_port or 8377

    try:
        if use_sse:
            logger.info(f"Starting Ripen Hub on {args.host}:{port}")
            mcp.run(transport="sse", host=args.host, port=port)
        else:
            # Proxy Mode
            target_hub = args.hub_url_pos
            if not target_hub or "<" in target_hub:
                target_hub = f"http://127.0.0.1:{port}"
            
            logger.info(f"Starting STDIO Proxy -> {target_hub}")
            asyncio.run(run_stdio_proxy(target_hub))
    except Exception as e:
        import traceback
        logger.critical(f"FATAL ERROR: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()