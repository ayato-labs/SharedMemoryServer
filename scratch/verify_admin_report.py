import asyncio
import json

from shared_memory import logic
from shared_memory.database import init_db
from shared_memory.thought_logic import init_thoughts_db


async def verify_admin_report():
    print("--- Initializing Databases ---")
    await init_db()
    await init_thoughts_db()

    print("\n--- Testing Admin Report (Markdown) ---")
    md_report = await logic.get_value_report_core(format_type="markdown")
    print(md_report[:500] + "...")

    print("\n--- Testing Admin Report (JSON) ---")
    json_report = await logic.get_value_report_core(format_type="json")
    print(json.dumps(json_report, indent=2))

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_admin_report())
