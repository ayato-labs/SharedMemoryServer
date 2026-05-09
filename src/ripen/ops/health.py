import os
import shutil
import time
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from ripen.common.utils import get_bank_dir, get_db_path, log_error
from ripen.infra.database import async_get_connection


async def check_db_health() -> dict[str, Any]:
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

    async with await async_get_connection() as conn:
        try:
            # Get page stats
            cursor = await conn.execute("PRAGMA page_count")
            stats["page_count"] = (await cursor.fetchone())[0]
            cursor = await conn.execute("PRAGMA page_size")
            stats["page_size"] = (await cursor.fetchone())[0]

            # Check WAL mode
            cursor = await conn.execute("PRAGMA journal_mode")
            stats["wal_mode"] = (await cursor.fetchone())[0].lower() == "wal"

            # Check fragmentation (freelist pages)
            cursor = await conn.execute("PRAGMA freelist_count")
            freelist_count = (await cursor.fetchone())[0]
            if stats["page_count"] > 0:
                stats["fragmentation_ratio"] = freelist_count / stats["page_count"]

            # Entity count for sanity
            cursor = await conn.execute("SELECT COUNT(*) FROM entities")
            stats["entities_count"] = (await cursor.fetchone())[0]
            stats["status"] = "healthy"

        except aiosqlite.Error as e:
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
        # Lightweight test: embed a tiny string
        # FastEmbed is local, so this checks if the model is loaded
        # Gemini checks network connectivity
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
        # We don't want to generate a full response, so we just check if it's reachable
        # For Ollama, we check the base URL. For Gemini, we check the client.
        if settings.llm_provider == "ollama":
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{settings.ollama_base_url}/api/tags") as resp:
                    if resp.status == 200:
                        status = "healthy"
                    else:
                        status = "unhealthy"
        else:
            # Gemini health check (Legacy logic)
            from ripen.infra.embeddings import get_gemini_client

            client = get_gemini_client()
            if client:
                status = "healthy"
            else:
                status = "unhealthy"

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


async def get_comprehensive_diagnostics() -> dict[str, Any]:
    """
    Aggregates all health checks into a single report.
    """
    db = await check_db_health()
    disk = await check_disk_usage()
    providers = await check_provider_health()

    overall_status = "healthy"
    issues = []

    if db["fragmentation_ratio"] > 0.3:
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
