import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from shared_memory.troubleshooting import (
    save_troubleshooting_record,
    search_troubleshooting_history,
)
from shared_memory.database import init_db


async def test_troubleshooting():
    log_lines = []
    log_lines.append("Initializing DB...")
    init_db()

    log_lines.append("Saving test troubleshooting record...")
    title = "Audio TranscriptionReputationRepetition Repetition Repetition"
    solution = "Adjusted VAD threshold from 0.5 to 0.8 and cleared buffer every 10s."
    env = {"os": "Windows 11", "python": "3.11", "lib": {"soundcard": "0.4.3"}}

    rec_id = await save_troubleshooting_record(title, solution, env_metadata=env)
    log_lines.append(f"Saved record ID: {rec_id}")

    log_lines.append("Searching for 'audio transcription issue'...")
    results = await search_troubleshooting_history("audio transcription issue")

    for res in results:
        log_lines.append(f"Match: {res['title']} (Score: {res['score']:.4f})")
        log_lines.append(f"Solution: {res['solution']}")
        log_lines.append(f"Env: {res['env_metadata']}")
        log_lines.append("-" * 20)

    with open("verify_results.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    asyncio.run(test_troubleshooting())
