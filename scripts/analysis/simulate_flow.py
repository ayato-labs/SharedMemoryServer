import asyncio
import os
import sys

# Setup paths
project_root = os.getcwd()
sys.path.insert(0, os.path.join(project_root, "src"))

from shared_memory.logic import read_memory_core, save_memory_core  # noqa: E402
from shared_memory.thought_logic import process_thought_core  # noqa: E402


async def simulate_behavior():
    session_id = f"analysis_demo_{os.urandom(4).hex()}"
    print(f"Starting analysis session: {session_id}")

    # Phase 1: Thinking (Hypothesis)
    # This will trigger a search and record metadata
    print("\n[Phase 1] Thinking about 'Anomaly Detection'...")
    await process_thought_core(
        thought=(
            "I suspect there is a correlation between low liquidity "
            "and sudden price spikes in JPY pairs. Checking past knowledge."
        ),
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id=session_id,
    )

    # Phase 2: Saving Knowledge (Discovery)
    # This will record vector and conflict metadata
    print("\n[Phase 2] Saving fact about 'JPY Volatility'...")
    await save_memory_core(
        entities=[
            {
                "name": "JPY Volatility Spike",
                "entity_type": "Observation",
                "description": ("Detecting 2% move within 5 minutes in USD/JPY."),
            }
        ],
        agent_id="analysis_agent",
    )

    # Phase 3: Retrieval (Verification)
    # This will record search stats
    print("\n[Phase 3] Retrieving the saved observation...")
    _ = await read_memory_core(query="Tell me about JPY volatility spikes")

    print("\nSimulation Complete. Analyzing traces...")


if __name__ == "__main__":
    asyncio.run(simulate_behavior())
