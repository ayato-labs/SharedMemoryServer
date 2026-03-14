# Tech Context

## Stack
- **Language**: Python (uv managed).
- **Core MCP Framework**: FastMCP.
- **Graph Storage**: SQLite (with Foreign Key enforcement).
- **Context Storage**: Markdown (aiofiles).
- **Logic Storage**: SQLite + FAISS (LogicHive).

## Constraints
- **Windows OS**: Requires explicit path handling for Docker and Subprocesses.
- **Statelessness**: Favor environment variables for configuration.
