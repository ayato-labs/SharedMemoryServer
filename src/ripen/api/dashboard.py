import os

from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Router

from ripen.api.licensing import LicenseManager
from ripen.common.config import settings
from ripen.common.utils import get_resource_path
from ripen.infra.embeddings import check_embeddings_health
from ripen.infra.llm import get_llm_provider
from ripen.infra.uow import SecureWriteContext, UnitOfWork
from ripen.ops import management


async def get_dashboard_html(_request):
    """Loads the dashboard HTML from templates and returns it."""
    # Use get_resource_path to ensure it works in both source and frozen EXE modes
    template_path = get_resource_path(os.path.join("api", "templates", "dashboard.html"))

    try:
        with open(template_path, encoding="utf-8") as f:
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
        # Use explicit keyword arguments to avoid positional mismatch
        history = await management.get_audit_history_logic(limit=limit, table_name=None, uow=uow)
    return JSONResponse(history)


async def api_conflicts(_request):
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


async def api_health(_request):
    llm = get_llm_provider()
    llm_ok = await llm.check_health()

    vector_ok = await check_embeddings_health()

    lm = LicenseManager()
    is_licensed = lm.validate_locally()
    license_info = lm.get_status_summary()

    return JSONResponse(
        {
            "llm": {"status": "ok" if llm_ok else "failed", "provider": llm.__class__.__name__},
            "vector": {
                "status": "ok" if vector_ok else "failed",
                "engine": settings.embedding_engine,
            },
            "license": {
                "status": "active" if is_licensed else "trial",
                "summary": license_info
            },
            "system": "online",
        }
    )


async def api_activate_license(request):
    try:
        body = await request.json()
        key_content = body.get("key")
        if not key_content:
            return JSONResponse(
                {"status": "error", "message": "No key content provided"},
                status_code=400,
            )

        lm = LicenseManager()

        # Save temp file to activate
        temp_path = settings.base_dir / "temp_dashboard_license.rpn"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(key_content.strip())

        success = lm.activate(temp_path)
        if temp_path.exists():
            os.remove(temp_path)

        if success:
            return JSONResponse({"status": "success", "message": "License activated successfully!"})
        else:
            return JSONResponse(
                {
                    "status": "error",
                    "message": "Invalid license key or signature verification failed.",
                },
                status_code=400,
            )
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


router = Router(
    [
        Route("/", get_dashboard_html, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/conflicts", api_conflicts, methods=["GET"]),
        Route("/api/resolve/{id:int}", api_resolve_conflict, methods=["POST"]),
        Route("/api/health", api_health, methods=["GET"]),
        Route("/api/license/activate", api_activate_license, methods=["POST"]),
    ]
)
