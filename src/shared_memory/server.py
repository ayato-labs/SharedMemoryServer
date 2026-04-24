import logging
import os
import sys
import argparse
import asyncio

# ruff: noqa: E402

# Save real stdout for MCP communication later
_REAL_STDOUT = sys.stdout
# Redirect sys.stdout to stderr to catch any noise from libraries during import
sys.stdout = sys.stderr

# Emergency logging setup - must be before other imports to catch their errors
# Ensure logs directory exists
LOG_DIR = "C:/Users/saiha/My_Service/programing/MCP/SharedMemoryServer/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "server.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=LOG_FILE,
    filemode="a",
)
logger = logging.getLogger("shared_memory.server")
logger.info("--- SERVER SCRIPT INITIALIZING (Robust Mode) ---")

from typing import Any

from fastmcp import FastMCP

# Delayed imports to catch potential errors in submodules
try:
    from shared_memory import logic, thought_logic
    from shared_memory.database import close_all_connections, init_db

    logger.info("Core submodules imported successfully")
except Exception as e:
    logger.error(f"CRITICAL: Failed to import submodules: {e}", exc_info=True)
    sys.exit(1)

# Create MCP server instance
mcp = FastMCP("SharedMemoryServer")

# Global initialization state
_INITIALIZED_EVENT = asyncio.Event()
_INIT_ERROR = None


async def _background_init():
    """Heavy lifting initialization in the background."""
    global _INIT_ERROR
    try:
        logger.info("Starting background initialization (DB, Graphs)...")
        await init_db()
        await thought_logic.init_thoughts_db()
        logger.info("Background initialization COMPLETE.")
    except Exception as e:
        _INIT_ERROR = e
        logger.error(f"Background initialization FAILED: {e}", exc_info=True)
    finally:
        _INITIALIZED_EVENT.set()


_INIT_STARTED = False

def trigger_init():
    global _INIT_STARTED
    if not _INIT_STARTED:
        _INIT_STARTED = True
        logger.info("Triggering background initialization...")
        asyncio.create_task(_background_init())


async def ensure_initialized():
    """Wait for background initialization if it's still running."""
    trigger_init()

    if not _INITIALIZED_EVENT.is_set():
        logger.info("Tool called before initialization finished. Waiting...")
        await _INITIALIZED_EVENT.wait()
    
    if _INIT_ERROR:
        from shared_memory.exceptions import DatabaseError
        raise DatabaseError(f"System failed to initialize: {_INIT_ERROR}")


@mcp.lifespan()
async def lifespan(mcp_instance: FastMCP):
    """
    Handles server startup and shutdown.
    Ensures handshake is fast by moving DB init to background.
    """
    # Start init in background if not already started
    trigger_init()

    yield

    # CLEANUP: Close persistent singleton connections on shutdown
    logger.info("Shutting down server, closing connections...")
    await close_all_connections()


# ==========================================
# CORE AGENT TOOLS (Standard Interface)
# ==========================================


@mcp.tool()
async def save_memory(
    entities: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    observations: list[dict[str, Any]] | None = None,
    bank_files: Any | None = None,
    agent_id: str = "default_agent",
) -> str:
    """
    Saves multiple pieces of knowledge in one transaction.

    - entities: List of entities with 'name' (required), 'entity_type', 'description'.
    - relations: Knowledge Graph Triples. Each dict MUST have:
        'subject' (source), 'object' (target), 'predicate' (type).
    - observations: List of factual statements linked to an entity.
    - bank_files: Markdown documentation. Supports two formats:
        1. Dictionary: { "filename.md": "content" }
        2. List of objects: [ { "filename": "filename.md", "content": "content" } ]
    """
    await ensure_initialized()
    return await logic.save_memory_core(entities, relations, observations, bank_files, agent_id)


@mcp.tool()
async def read_memory(query: str | None = None):
    """
    Retrieves knowledge from the graph and memory bank.
    Uses hybrid search (Semantic + Keyword) if a query is provided.
    """
    await ensure_initialized()
    return await logic.read_memory_core(query)


@mcp.tool()
async def get_graph_data(query: str = None) -> dict[str, Any] | str:
    """
    Retrieves knowledge from the graph database.
    Optionally filters graph data based on a query.
    """
    await ensure_initialized()
    try:
        return await logic.graph.get_graph_data(query)
    except Exception as e:
        return f"Database Error: Failed to retrieve graph data. {e}"


@mcp.tool()
async def synthesize_entity(entity_name: str):
    """Aggregates all known info about an entity into a master summary."""
    await ensure_initialized()
    return await logic.synthesize_entity(entity_name)


@mcp.tool()
async def manage_knowledge_activation(ids: list[str], status: str):
    """
    Manages the activation state of knowledge items (entities, bank files, etc.).
    - status: 'active' (default/searchable), 'inactive' (hidden), or 'archived' (legacy).
    Use this to toggle knowledge OFF/ON without destructive deletion.
    """
    await ensure_initialized()
    return await logic.manage_knowledge_activation_core(ids, status)


@mcp.tool()
async def list_inactive_knowledge():
    """
    Lists all knowledge assets that are currently inactive or archived.
    Useful for reviewing what information has been sidelined or for potential reactivation.
    """
    await ensure_initialized()
    return await logic.list_inactive_knowledge_core()


# ==========================================
# THOUGHT & REASONING TOOLS
# ==========================================


@mcp.tool()
async def sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: bool | None = False,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    session_id: str = "default_session",
):
    """
    A detailed tool for dynamic and reflective problem-solving through thoughts.
    Each thought can build on, question, or revise previous insights as
    understanding deepens.
    Automatically surfaces related past memories and thoughts to enrich the
    reasoning process.

    COMMIT ADVISORY: After completing a significant reasoning milestone or
    making fundamental design decisions, you should promptly COMMIT your
    code changes to ensure traceability. Summarize your reasoning in the
    commit message.
    """
    await ensure_initialized()
    return await thought_logic.process_thought_core(
        thought,
        thought_number,
        total_thoughts,
        next_thought_needed,
        is_revision,
        revises_thought,
        branch_from_thought,
        branch_id,
        session_id,
    )


@mcp.tool()
async def get_insights(format: str = "markdown"):
    """
    SharedMemoryServerの導入効果（価値）を定量化したレポートを取得します。
    - format: 'markdown' (人間向けレポート) または 'json' (プログラム用データ)
    ビジネス上のROIやトークン削減量、知識の再利用率を確認するために使用します。
    """
    await ensure_initialized()
    from shared_memory.insights import InsightEngine

    metrics = await InsightEngine.get_summary_metrics()
    if format == "json":
        return metrics
    return InsightEngine.generate_report_markdown(metrics)


@mcp.tool()
async def check_integrity():
    """
    Performs a comprehensive integrity check of the LogicHive system,
    including DB status, Vector store synchronization, and Environment pools.
    """
    await ensure_initialized()
    from shared_memory.health import get_comprehensive_diagnostics

    return await get_comprehensive_diagnostics()


@mcp.tool()
async def ping() -> str:
    return "pong"


def main():
    """Entry point for the MCP server with enhanced stability and SSE support."""
    parser = argparse.ArgumentParser(description="SharedMemoryServer MCP")
    parser.add_argument("--sse", action="store_true", help="Run with SSE transport")
    parser.add_argument("--port", type=int, default=8377, help="Port for SSE server")
    args = parser.parse_args()

    # Determine transport
    use_sse = args.sse or os.environ.get("MCP_TRANSPORT") == "sse"

    if not use_sse:
        # Restore stdout for MCP communication ONLY in stdio mode
        sys.stdout = _REAL_STDOUT
        # Ensure output is unbuffered to prevent connection hangs
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
        logger.info("SharedMemoryServer: Starting in STDIO mode")
    else:
        logger.info(f"SharedMemoryServer: Starting in SSE mode on port {args.port}")

    # Silence internal MCP and FastMCP loggers to prevent any stray output
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("fastmcp").setLevel(logging.WARNING)

    try:
        if use_sse:
            mcp.run(transport="sse", port=args.port)
        else:
            # transport="stdio" is default
            mcp.run(transport="stdio")
    except Exception:
        logger.exception("CRITICAL: Server crashed in mcp.run()")
        sys.exit(1)


if __name__ == "__main__":
    main()
