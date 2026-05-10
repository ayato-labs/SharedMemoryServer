import os
import shutil
import time
from datetime import UTC, datetime
from typing import Any

from ripen.common.utils import get_bank_dir, get_db_path, log_error


async def check_db_health(uow) -> dict[str, Any]:
    """
    Checks the physical health and fragmentation of the SQLite database.
    """
    db_path = get_db_path()
    stats = {
        "path": db_path,
        "status": "unhealthy",
        "size_bytes": 0,
        "page_count": 0,
        "page_size": 0,
        "fragmentation_ratio": 0.0,
        "wal_mode": False,
        "entities_count": 0,
    }

    if not os.path.exists(db_path):
        return stats

    stats["size_bytes"] = os.path.getsize(db_path)

    try:
        db_stats = await uow.management.get_database_stats()
        stats.update(db_stats)

        # Entity count for sanity
        stats["entities_count"] = await uow.management.get_count("entities")
        stats["status"] = "healthy"
    except Exception as e:
        log_error("Failed to check DB health", e)

    return stats


async def check_disk_usage() -> dict[str, Any]:
    """
    Checks available disk space for the memory bank.
    """
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir, exist_ok=True)

    usage = shutil.disk_usage(bank_dir)
    return {
        "dir": bank_dir,
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent_free": (usage.free / usage.total) * 100 if usage.total > 0 else 0,
    }


async def check_provider_health() -> dict[str, Any]:
    """
    Verifies connectivity and readiness of the configured LLM and Embedding providers.
    """
    from ripen.common.config import settings
    from ripen.infra.embeddings import compute_embedding

    results = {}

    # 1. Check Embedding Engine
    emb_start = time.time()
    try:
        vec = await compute_embedding("health_check")
        results["embedding"] = {
            "engine": settings.embedding_engine,
            "status": "healthy" if vec else "unhealthy",
            "latency_ms": (time.time() - emb_start) * 1000,
        }
    except Exception as e:
        results["embedding"] = {
            "engine": settings.embedding_engine,
            "status": "unhealthy",
            "error": str(e),
        }

    # 2. Check LLM Provider
    llm_start = time.time()
    try:
        if settings.llm_provider == "ollama":
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{settings.ollama_base_url}/api/tags") as resp:
                    status = "healthy" if resp.status == 200 else "unhealthy"
        else:
            from ripen.infra.embeddings import get_gemini_client

            client = get_gemini_client()
            status = "healthy" if client else "unhealthy"

        results["llm"] = {
            "provider": settings.llm_provider,
            "status": status,
            "latency_ms": (time.time() - llm_start) * 1000,
        }
    except Exception as e:
        results["llm"] = {
            "provider": settings.llm_provider,
            "status": "unhealthy",
            "error": str(e),
        }

    return results


async def get_comprehensive_diagnostics(uow) -> dict[str, Any]:
    """
    Aggregates all health checks into a single report.
    """
    db = await check_db_health(uow)
    disk = await check_disk_usage()
    providers = await check_provider_health()

    overall_status = "healthy"
    issues = []

    if db.get("fragmentation_ratio", 0) > 0.3:
        issues.append("High DB fragmentation detected. VACUUM recommended.")
    if disk["percent_free"] < 10:
        overall_status = "warning"
        free_gb = disk["free"] / (1024**3)
        issues.append(f"Low disk space on host drive. Remaining: {free_gb:.1f} GB.")

    if providers["embedding"]["status"] != "healthy":
        overall_status = "unhealthy"
        issues.append(f"Embedding ({providers['embedding']['engine']}) is unhealthy")

    if providers["llm"]["status"] != "healthy":
        overall_status = "unhealthy"
        issues.append(f"LLM Provider ({providers['llm']['provider']}) is unreachable")

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "db_status": "healthy" if db["status"] == "healthy" else "unhealthy",
        "disk_status": "healthy" if disk["percent_free"] > 5 else "warning",
        "issues": issues,
        "components": {"database": db, "storage": disk, "providers": providers},
    }
