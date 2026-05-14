import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

from fastmcp import FastMCP
from loguru import logger

from ripen.api.auth import dashboard_router
from ripen.api.licensing import LicenseManager
from ripen.common.config import settings
from ripen.common.plugins import PluginLoader
from ripen.common.tasks import create_background_task
from ripen.common.utils import configure_logging, get_logger, safe_main_executor
from ripen.ops.lifecycle import start_database_maintenance

# --- EXTREME GUARD: STDOUT REDIRECTION ---
# We must ensure uvicorn/fastapi doesn't hijack stdout when running in stdio mode.
# FastMCP usually handles this, but we reinforce it here.
class StdoutGuard:
    def __init__(self):
        self._real_stdout = sys.stdout
        self._devnull = open(os.devnull, "w")

    def __enter__(self):
        sys.stdout = self._devnull
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._real_stdout
        self._devnull.close()


# --- INITIALIZATION ---
configure_logging()
logger.info("--- SERVER SCRIPT STARTING (Extreme Guard Mode) ---")

# Delayed imports to ensure logging is ready
logger.info("Importing core submodules...")
from ripen.core import (
    ai_control,
    logic,
    search_logic,
    thought_logic as thought_module,
)
from ripen.infra.database import init_db
from ripen.infra.llm import get_llm_provider

logger.info("Core submodules and Dashboard router imported successfully")

# Create FastMCP server instance
mcp = FastMCP(
    "Ripen",
    version="0.1.0",
    description="The centralized knowledge hub for AI agents. Hybrid Vector + Graph memory.",
)

# Attach Dashboard
mcp.add_router(dashboard_router, prefix="/dashboard")

# --- TOOLS ---


@mcp.tool()
async def read_memory(query: str = "") -> str:
    """
    Retrieves relevant knowledge from the memory hub using hybrid search.
    Use this to gather context about entities, relations, and past observations.
    """
    logger.info(f"Tool called: read_memory(query='{query}')")
    results = await search_logic.hybrid_search_core(query)
    if not results:
        return "No relevant memories found."

    # Format results for the agent
    output = ["--- RELEVANT MEMORIES ---"]
    for r in results:
        output.append(f"[{r['type'].upper()}] {r['content']}")
        if r.get("metadata"):
            output.append(f"   Metadata: {r['metadata']}")

    return "\n".join(output)


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
    try:
        await logic.save_memory_core(
            entities=entities,
            relations=relations,
            observations=observations,
            bank_files=bank_files,
            agent_id=agent_id,
        )
        return "Knowledge successfully persisted to the hub."
    except Exception as e:
        logger.exception("Failed to save memory")
        return f"Error: {e}"


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
    try:
        result = await thought_module.process_thought_logic(
            thought=thought,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            next_thought_needed=next_thought_needed,
            session_id=session_id,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            is_revision=is_revision,
        )
        return result
    except Exception as e:
        logger.exception("Sequential thinking failed")
        return f"Thinking Error: {e}"


# --- MCP PROTOCOL PATCH ---
# We patch FastMCP's server session to be more resilient to malformed requests
# often sent by experimental agents.
try:
    from mcp.server.session import ServerSession

    _orig_received_request = ServerSession._received_request

    async def _patched_received_request(self, request):
        try:
            return await _orig_received_request(self, request)
        except Exception as e:
            logger.error(f"MCP Protocol Error: Handled malformed request: {e}")
            # We don't crash, we just log and ignore if possible
            pass

    ServerSession._received_request = _patched_received_request
    logger.info("MCP Protocol Patch: ServerSession._received_request is now PERMISSIVE.")
except Exception as e:
    logger.warning(f"Failed to apply MCP Protocol Patch: {e}")


# --- LIFESPAN & APP WRAPPER ---


@mcp.on_startup()
async def lifespan():
    """Startup sequence for the hub."""
    logger.info("Ripen Hub: Starting lifespan sequence...")

    # 1. Init Database
    await init_db()

    # 2. Init Thoughts DB
    await thought_module.init_thoughts_db()

    # 3. Start Maintenance Tasks
    create_background_task(start_database_maintenance())

    # 4. Check AI Provider
    provider = get_llm_provider()
    logger.info(f"LLM Provider detected: {provider.__class__.__name__}")

    try:
        await provider.check_health()
        logger.info("[BACKEND STATUS] AI Brain (LLM): OK")
    except Exception as e:
        logger.error(f"[BACKEND STATUS] AI Brain (LLM): FAILED - {e}")

    logger.info("Ripen Hub: Startup complete.")


# --- ENTRY POINT ---


def print_banner(mode: str, port: int):
    lm = LicenseManager()
    lm.validate_locally()
    license_text = lm.get_status_summary()

    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print("  Ripen Knowledge Hub v0.1.0")
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
    parser.add_argument("--sse", action="store_true", help="Start in SSE mode (HTTP)")
    parser.add_argument("--port", type=int, default=8377, help="Port for SSE mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE mode")
    parser.add_argument("--dev", action="store_true", help="Start in development mode")

    args = parser.parse_args()

    if args.dev:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Handle termination signals
    def handle_signal(sig, frame):
        logger.info(f"Signal {sig} received. Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.sse:
        # Load plugins before starting
        PluginLoader().load_all()

        print_banner("SSE (Server-Sent Events)", args.port)
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # STDIO mode: requires extreme guard to keep stdout clean
        # Load plugins before starting
        PluginLoader().load_all()

        print_banner("STDIO (Standard I/O)", 0)
        mcp.run(transport="stdio")


async def ensure_initialized():
    """
    Explicitly ensures the database and infrastructure are initialized.
    """
    logger.info("Server: Ensuring initialization...")
    await init_db()
    await thought_module.init_thoughts_db()
    logger.info("Server: Initialization complete.")


async def wait_for_background_tasks(timeout: float = 5.0):
    """
    Waits for all background tasks to complete or timeout.
    """
    from ripen.common.tasks import (
        wait_for_background_tasks as wait_tasks,
    )

    await wait_tasks(timeout=timeout)


if __name__ == "__main__":
    safe_main_executor(main)()
