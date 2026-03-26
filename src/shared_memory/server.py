from typing import Any

from fastmcp import FastMCP

from shared_memory import logic, thought_logic
from shared_memory.database import init_db

mcp = FastMCP("SharedMemoryServer")


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
    Highly recommended for complex updates to maintain consistency.
    """
    return await logic.save_memory_core(
        entities, relations, observations, bank_files, agent_id
    )


@mcp.tool()
async def get_graph_data(query: str = None) -> dict[str, Any]:
    """
    Retrieves knowledge from the graph database.
    Optionally filters graph data based on a query.
    """
    return await logic.graph.get_graph_data(query)


@mcp.tool()
async def read_memory(query: str | None = None):
    """
    Retrieves knowledge from the graph and memory bank.
    Uses hybrid search (Semantic + Keyword) if a query is provided.
    """
    return await logic.read_memory_core(query)


@mcp.tool()
async def get_audit_history(limit: int = 20, table_name: str | None = None):
    """Returns recent changes to the knowledge base."""
    return await logic.get_audit_history_core(limit, table_name)


@mcp.tool()
async def synthesize_entity(entity_name: str):
    """Aggregates all known info about an entity into a master summary."""
    return await logic.synthesize_entity(entity_name)


@mcp.tool()
async def rollback_memory(audit_id: int):
    """Restores an entry to its state in a specific audit log record."""
    return await logic.rollback_memory_core(audit_id)


@mcp.tool()
async def create_snapshot(name: str, description: str = ""):
    """Creates a full backup (recovery point) of the knowledge base."""
    return await logic.create_snapshot_core(name, description)


@mcp.tool()
async def restore_snapshot(snapshot_id: int):
    """Restores the database from a specific snapshot."""
    return await logic.restore_snapshot_core(snapshot_id)


@mcp.tool()
async def troubleshooting_record(
    problem_description: str,
    solution: str,
    env_metadata_json: str,
    tags: list[str] = [],
):
    """
    Records a troubleshooting session for future reference.
    Includes environment details (OS, versions) to ensure context preservation.
    """
    return await logic.troubleshooting_record_core(
        problem_description, solution, env_metadata_json, tags
    )


@mcp.tool()
async def troubleshooting_search(query: str):
    """Searches past troubleshooting sessions to find relevant fixes."""
    return await logic.troubleshooting_search_core(query)


@mcp.tool()
async def get_memory_health():
    """Returns diagnostics on knowledge density, gaps, and biases."""
    return await logic.get_memory_health_core()


@mcp.tool()
async def repair_memory():
    """Attempts to fix simple relational gaps or corrupted metadata."""
    return await logic.repair_memory_core()


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
    This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
    Each thought can build on, question, or revise previous insights as understanding deepens.
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


if __name__ == "__main__":
    init_db()
    thought_logic.init_thoughts_db()
    mcp.run()
