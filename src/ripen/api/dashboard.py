import os
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Router

from ripen.ops import management
from ripen.infra.uow import UnitOfWork, SecureWriteContext
from ripen.common.utils import get_resource_path


async def get_dashboard_html(request):
    """Loads the dashboard HTML from templates and returns it."""
    # Use get_resource_path to ensure it works in both source and frozen EXE modes
    template_path = get_resource_path(os.path.join("api", "templates", "dashboard.html"))

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body><h1>Dashboard Template Error</h1><p>{e}</p></body></html>",
            status_code=500,
        )

    return HTMLResponse(content=html_content)


async def api_history(request):
    limit = int(request.query_params.get("limit", 20))
    async with UnitOfWork() as uow:
        # Corrected order: (limit, table_name, uow)
        history = await management.get_audit_history_logic(limit, None, uow)
    return JSONResponse(history)


async def api_conflicts(request):
    async with UnitOfWork() as uow:
        conflicts = await management.get_unresolved_conflicts_logic(uow)
    return JSONResponse(conflicts)


async def api_resolve_conflict(request):
    conflict_id = int(request.path_params.get("id"))
    action = request.query_params.get("action", "approve")
    async with SecureWriteContext() as uow:
        # Corrected order: (conflict_id, action, uow)
        result = await management.resolve_conflict_logic(conflict_id, action, uow)
        await uow.commit()
    return JSONResponse({"status": "success", "message": result})


router = Router(
    [
        Route("/", get_dashboard_html, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/conflicts", api_conflicts, methods=["GET"]),
        Route("/api/resolve/{id:int}", api_resolve_conflict, methods=["POST"]),
    ]
)
