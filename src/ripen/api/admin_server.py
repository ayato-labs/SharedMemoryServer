from fastmcp import FastMCP

from ripen.core import logic, thought_logic
from ripen.infra.database import init_db

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


from ripen.infra.uow import UnitOfWork, SecureWriteContext

# ==========================================
# ADMIN & MAINTENANCE TOOLS
# ==========================================


@mcp.tool()
async def admin_get_audit_history(limit: int = 20, table_name: str | None = None):
    """Retrieves the history of all changes made to the memory."""
    async with UnitOfWork() as uow:
        return await logic.get_audit_history_core(limit, table_name, uow)


@mcp.tool()
async def admin_get_memory_health():
    """Performs deep diagnostics on database, storage, and API connectivity."""
    async with UnitOfWork() as uow:
        return await logic.get_memory_health_core(uow)


@mcp.tool()
async def admin_repair_memory():
    """Syncs the file bank from the database to recover lost or corrupted files."""
    async with SecureWriteContext() as uow:
        res = await logic.repair_memory_core(uow)
        await uow.commit()
    return res


@mcp.tool()
async def admin_rollback_memory(audit_id: int):
    """Reverts a specific change based on its audit log ID."""
    async with SecureWriteContext() as uow:
        res = await logic.rollback_memory_core(audit_id, uow)
        await uow.commit()
    return res


@mcp.tool()
async def admin_create_snapshot(name: str, description: str = ""):
    """Creates a point-in-time backup of the entire memory database."""
    async with SecureWriteContext() as uow:
        res = await logic.create_snapshot_core(name, description, uow)
        await uow.commit()
    return res


@mcp.tool()
async def admin_restore_snapshot(snapshot_id: int):
    """Restores the database to a previously created snapshot."""
    async with SecureWriteContext() as uow:
        res = await logic.restore_snapshot_core(snapshot_id, uow)
        await uow.commit()
    return res


@mcp.tool()
async def admin_get_value_report(format_type: str = "markdown"):
    """
    Returns an objective value report (Fact-Based) of the memory server.
    """
    async with UnitOfWork() as uow:
        return await logic.get_value_report_core(uow, format_type)


@mcp.tool()
async def admin_run_knowledge_gc(age_days: int = 180, dry_run: bool = False):
    """
    Manually triggers the Knowledge Garbage Collection (GC) logic.
    """
    async with SecureWriteContext() as uow:
        res = await logic.admin_run_knowledge_gc_core(uow, age_days, dry_run)
        await uow.commit()
    return res


def main():
    """Entry point for the Admin MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
