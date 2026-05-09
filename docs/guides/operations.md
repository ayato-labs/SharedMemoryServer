# Operations Manual

Guidelines for maintaining system integrity and performance.

## 1. System Health Checks
Run the built-in diagnostic suite to verify 16 core functionalities (Concurrency, Atomic Sync, Retrieval):
```bash
uv run pytest tests -v
```

## 2. Database Maintenance
SharedMemoryServer uses SQLite with WAL (Write-Ahead Logging) mode for high concurrency.
- **Location**: `data/shared_memory.db`
- **Backup**: Simply copy the `.db` file while the server is stopped.
- **Integrity**: Use the `admin_repair` tool to reconstruct the Graph from Memory Bank mirrors if corruption occurs.

## 3. Log Management
Logs are stored in `logs/server.log`.
- **Initialization Issues**: Search for `Database locked` or `API Error`.
- **Performance Tuning**: Monitor `Compute-then-Write` latency markers.

## 4. Troubleshooting

### 4-1. Server Hangs (Lock Contention)
If a tool does not respond, an orphaned process might be holding the DB lock.
- **Windows**: `Get-Process python | Stop-Process -Force`
- **Linux/macOS**: `pkill -f shared-memory`

### 4-2. API Rate Limits (429)
The server implements **Intelligent Retry** with exponential backoff. If failures persist, check your Google Cloud Console quota.

### 4-3. Sync Failures
If the Memory Bank (Markdown) and Knowledge Graph (DB) drift, run:
1. `admin_create_snapshot`
2. `admin_repair`

---
*For architectural details, see [Architecture](architecture.md).*
