from typing import Any

from fastmcp import FastMCP

from shared_memory import logic, thought_logic
from shared_memory.database import close_all_connections, init_db

# Create MCP server instance (Agent Data Plane)
mcp = FastMCP("SharedMemoryServer")


# ==========================================
# LIFESPAN & INITIALIZATION
# ==========================================


@mcp.lifespan()
async def lifespan(mcp_instance: FastMCP):
    """
    Handles server startup and shutdown.
    Ensures databases are initialized before tools are called.
    """
    await init_db()
    await thought_logic.init_thoughts_db()

    yield

    # CLEANUP: Close persistent singleton connections on shutdown
    await close_all_connections()


# ==========================================
# CORE AGENT TOOLS (Standard Interface)
# ==========================================


@mcp.tool()
async def save_memory(
    entities: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    observations: list[dict[str, Any]] | None = None,
    bank_files: dict[str, str] | None = None,
    agent_id: str = "default_agent",
) -> str:
    """
    Saves multiple pieces of knowledge in one transaction.

    - entities: List of entities with 'name' (required), 'entity_type', 'description'.
    - relations: Knowledge Graph Triples. Each dict MUST have:
        'subject' (source), 'object' (target), 'predicate' (type).
    - observations: List of factual statements linked to an entity.
    - bank_files: Markdown documentation to be saved in the memory bank.
    """
    return await logic.save_memory_core(
        entities, relations, observations, bank_files, agent_id
    )


@mcp.tool()
async def read_memory(query: str | None = None):
    """
    Retrieves knowledge from the graph and memory bank.
    Uses hybrid search (Semantic + Keyword) if a query is provided.
    """
    return await logic.read_memory_core(query)


@mcp.tool()
async def get_graph_data(query: str = None) -> dict[str, Any]:
    """
    Retrieves knowledge from the graph database.
    Optionally filters graph data based on a query.
    """
    await init_db()
    await thought_logic.init_thoughts_db()
    return await logic.graph.get_graph_data(query)


@mcp.tool()
async def synthesize_entity(entity_name: str):
    """Aggregates all known info about an entity into a master summary."""
    return await logic.synthesize_entity(entity_name)


@mcp.tool()
async def manage_knowledge_activation(ids: list[str], status: str):
    """
    Manages the activation state of knowledge items (entities, bank files, etc.).
    - status: 'active' (default/searchable), 'inactive' (hidden), or 'archived' (legacy).
    Use this to toggle knowledge OFF/ON without destructive deletion.
    """
    return await logic.manage_knowledge_activation_core(ids, status)


@mcp.tool()
async def list_inactive_knowledge():
    """
    Lists all knowledge assets that are currently inactive or archived.
    Useful for reviewing what information has been sidelined or for potential reactivation.
    """
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
    from shared_memory.insights import InsightEngine

    metrics = await InsightEngine.get_summary_metrics()
    if format == "json":
        return metrics
    return InsightEngine.generate_report_markdown(metrics)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
