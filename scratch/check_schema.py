
import asyncio
from typing import Any
from fastmcp import FastMCP
import json

mcp = FastMCP("TestServer")

@mcp.tool()
async def save_memory(
    entities: list[dict] = [],
    relations: list[dict] = [],
    observations: list[dict] = [],
    bank_files: dict[str, str] = {},
    agent_id: str = "default_agent",
) -> str:
    return "ok"

async def main():
    tools = await mcp.list_tools()
    for tool in tools:
        print(f"Tool: {tool.name}")
        if hasattr(tool, "parameters"):
             print(f"Parameters: {tool.parameters}")

if __name__ == "__main__":
    asyncio.run(main())
