import asyncio
import os
import sys

from datasets import Dataset
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

# Ensure SharedMemoryServer is in path
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory.database import init_db
from shared_memory.server import read_memory, save_memory, synthesize_entity


async def run_debug():
    load_dotenv()
    print(f"API KEY EXISTS: {bool(os.environ.get('GOOGLE_API_KEY'))}")
    init_db()

    # Configure Ragas
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    ragas_llm = LangchainLLMWrapper(llm)
    for m in [faithfulness, answer_relevancy, context_precision, context_recall]:
        m.llm = ragas_llm

    # Setup
    await save_memory(
        entities=[{"name": "Project Apollo", "description": "High-speed transcription."}],
        observations=[{"entity_name": "Project Apollo", "content": "Uses Python 3.11"}],
    )

    # Eval
    search_res = await read_memory(query="Apollo")
    context_snippets = [
        f"Entity {e['name']}: {e['description']}" for e in search_res["graph"]["entities"]
    ]
    answer = await synthesize_entity(entity_name="Project Apollo")

    data = {
        "question": ["What technology does Project Apollo use?"],
        "answer": [answer],
        "contexts": [context_snippets],
        "ground_truth": ["Python 3.11"],
    }
    dataset = Dataset.from_dict(data)

    print("Starting Ragas evaluate...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    print(f"Ragas Result: {result}")


if __name__ == "__main__":
    asyncio.run(run_debug())
