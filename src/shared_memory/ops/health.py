import asyncio
import os
import time

import aiosqlite

from shared_memory.common.utils import get_db_path, get_logger, get_thoughts_db_path
from shared_memory.infra.database import async_get_connection

logger = get_logger(\"health\")


async def get_comprehensive_diagnostics():
    \"\"\"Performs a deep diagnostic of the system state.\"\"\"
    start_time = time.perf_counter()
    diag = {
        \"status\": \"healthy\",
        \"timestamp\": time.time(),
        \"databases\": {},
        \"file_system\": {},
        \"performance\": {},
    }

    # 1. Database Connectivity & Schema
    for db_name, path_func in [(\"main\", get_db_path), (\"thoughts\", get_thoughts_db_path)]:
        path = path_func()
        db_diag = {\"path\": path, \"exists\": os.path.exists(path)}
        if db_diag[\"exists\"]:
            try:
                db_diag[\"size_kb\"] = os.path.getsize(path) / 1024
                async with aiosqlite.connect(path) as conn:
                    cursor = await conn.cursor()
                    await cursor.execute(\"PRAGMA integrity_check\")
                    db_diag[\"integrity\"] = (await cursor.fetchone())[0]
            except Exception as e:
                db_diag[\"status\"] = \"error\"
                db_diag[\"error\"] = str(e)
                diag[\"status\"] = \"degraded\"
        diag[\"databases\"][db_name] = db_diag

    # 2. Connection Pool Check
    try:
        async with async_get_connection() as conn:
            await conn.execute(\"SELECT 1\")
            diag[\"databases\"][\"main\"][\"connection_pool\"] = \"active\"
    except Exception as e:
        diag[\"databases\"][\"main\"][\"connection_pool\"] = f\"failed: {e}\"

    diag[\"performance\"][\"diagnostic_latency_ms\"] = (time.perf_counter() - start_time) * 1000
    return diag
