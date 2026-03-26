import os
import shutil
import sqlite3
import time
from datetime import UTC
from typing import Any

from shared_memory.database import get_connection
from shared_memory.utils import get_bank_dir, get_db_path, log_error


async def check_db_health() -> dict[str, Any]:
    """
    Checks the physical health and fragmentation of the SQLite database.
    """
    db_path = get_db_path()
    stats = {
        "path": db_path,
        "size_bytes": 0,
        "page_count": 0,
        "page_size": 0,
        "fragmentation_ratio": 0.0,
        "wal_mode": False,
    }

    if not os.path.exists(db_path):
        return stats

    stats["size_bytes"] = os.path.getsize(db_path)

    conn = get_connection()
    try:
        # Get page stats
        cursor = conn.cursor()
        cursor.execute("PRAGMA page_count")
        stats["page_count"] = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        stats["page_size"] = cursor.fetchone()[0]

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode")
        stats["wal_mode"] = cursor.fetchone()[0].lower() == "wal"

        # Check fragmentation (freelist pages)
        cursor.execute("PRAGMA freelist_count")
        freelist_count = cursor.fetchone()[0]
        if stats["page_count"] > 0:
            stats["fragmentation_ratio"] = freelist_count / stats["page_count"]

    except sqlite3.Error as e:
        log_error("Failed to check DB health", e)
    finally:
        conn.close()

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


async def check_api_connectivity() -> dict[str, Any]:
    """
    Verifies connectivity to the embedding service.
    """
    from shared_memory.embeddings import get_gemini_client

    start_time = time.time()
    try:
        client = get_gemini_client()
        # Ping by listing models or similar lightweight operation
        # Note: listing models consumes a bit of quota but is safer than a dummy embed
        models = client.models.list()
        # Just check if we can iterate at least one
        next(iter(models))
        status = "healthy"
        error = None
    except Exception as e:
        status = "unhealthy"
        error = str(e)

    return {
        "service": "Google Gemini API",
        "status": status,
        "latency_ms": (time.time() - start_time) * 1000,
        "error": error,
    }


async def get_comprehensive_diagnostics() -> dict[str, Any]:
    """
    Aggregates all health checks into a single report.
    """
    db = await check_db_health()
    disk = await check_disk_usage()
    api = await check_api_connectivity()

    overall_status = "healthy"
    issues = []

    if db["fragmentation_ratio"] > 0.3:
        issues.append("High DB fragmentation detected. VACUUM recommended.")
    if disk["percent_free"] < 10:
        overall_status = "warning"
        issues.append("Low disk space in data storage directory.")
    if api["status"] != "healthy":
        overall_status = "unhealthy"
        issues.append(f"Gemini API connectivity issue: {api['error']}")

    from datetime import datetime

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "issues": issues,
        "components": {"database": db, "storage": disk, "api": api},
    }
