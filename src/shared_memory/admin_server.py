from fastmcp import FastMCP

from shared_memory import logic, thought_logic
from shared_memory.database import init_db

# Create MCP server instance (Control Plane / Admin)
mcp = FastMCP("SharedMemoryAdminServer")


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


# ==========================================
# ADMIN & MAINTENANCE TOOLS
# ==========================================


@mcp.tool()
async def admin_get_audit_history(limit: int = 20, table_name: str | None = None):
    """Retrieves the history of all changes made to the memory."""
    return await logic.get_audit_history_core(limit, table_name)


@mcp.tool()
async def admin_get_memory_health():
    """Performs deep diagnostics on database, storage, and API connectivity."""
    return await logic.get_memory_health_core()


@mcp.tool()
async def admin_repair_memory():
    """Syncs the file bank from the database to recover lost or corrupted files."""
    return await logic.repair_memory_core()


@mcp.tool()
async def admin_rollback_memory(audit_id: int):
    """Reverts a specific change based on its audit log ID."""
    return await logic.rollback_memory_core(audit_id)


@mcp.tool()
async def admin_create_snapshot(name: str, description: str = ""):
    """Creates a point-in-time backup of the entire memory database."""
    return await logic.create_snapshot_core(name, description)


@mcp.tool()
async def admin_restore_snapshot(snapshot_id: int):
    """Restores the database to a previously created snapshot."""
    return await logic.restore_snapshot_core(snapshot_id)


@mcp.tool()
async def admin_get_value_report(format_type: str = "markdown"):
    """
    Returns an objective value report (Fact-Based) of the memory server.
    :param format_type: 'markdown' (default) for report, 'json' for data.
    """
    return await logic.get_value_report_core(format_type)


@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False):
    """
    Manually triggers the Knowledge Garbage Collection (GC) logic.
    Moves 'active' items that are stale (low importance and old) to 'inactive'.
    """
    return await logic.admin_run_knowledge_gc_core(age_days, dry_run)


def main():
    """Entry point for the Admin MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
