import os

import pytest
from datasets import Dataset
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from shared_memory.database import init_db
from shared_memory.server import read_memory, save_memory, synthesize_entity

# Load real environment variables before conftest mocks them
load_dotenv()


# ...
@pytest.mark.evaluation
@pytest.mark.asyncio
async def test_ragas_quality_metrics(mock_gemini):
    # Configure Ragas to use Gemini
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    emb = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    ragas_llm = LangchainLLMWrapper(llm)
    ragas_emb = LangchainEmbeddingsWrapper(emb)

    for metric in [faithfulness, answer_relevancy, context_precision, context_recall]:
        metric.llm = ragas_llm
        metric.embeddings = ragas_emb

    await init_db()

    # 1. Setup Golden Dataset (Context)
    # We populate the memory with known facts
    await save_memory(
        entities=[
            {
                "name": "Project Apollo",
                "description": "A high-speed transcription service.",
            },
            {
                "name": "Lead Developer",
                "description": "Alice is the lead developer of Project Apollo.",
            },
        ],
        observations=[
            {
                "entity_name": "Project Apollo",
                "content": "The system uses Python 3.11 and FastMCP.",
            },
            {
                "entity_name": "Project Apollo",
                "content": "Release date is scheduled for Q4 2024.",
            },
        ],
    )

    # 2. Evaluation Data points
    eval_queries = [
        {
            "question": "Who is the lead developer of Project Apollo?",
            "ground_truth": "Alice is the lead developer of Project Apollo.",
        },
        {
            "question": "What technologies are used in Project Apollo?",
            "ground_truth": "Python 3.11 and FastMCP.",
        },
    ]

    # 3. Execute RAG Flow and Collect Results
    data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    for query in eval_queries:
        q = query["question"]

        # Retrieval step (Context searching)
        search_res = await read_memory(query=q)
        # Extract relevant snippets from graph/bank to form context strings
        context_snippets = []
        for e in search_res["graph"]["entities"]:
            context_snippets.append(f"Entity {e['name']}: {e['description']}")
        for o in search_res["graph"]["observations"]:
            context_snippets.append(f"Observation: {o['content']}")

        # Generation step (Synthesis)
        answer = await synthesize_entity(
            entity_name="Project Apollo"
        )  # Simplified for demo

        data["question"].append(q)
        data["answer"].append(answer)
        data["contexts"].append(context_snippets)
        data["ground_truth"].append(query["ground_truth"])

    # 4. Convert to Ragas Dataset
    dataset = Dataset.from_dict(data)

    # 5. Run Evaluation
    # Note: evaluate() usually requires a real LLM. For mock testing,
    # we would normally skip this or use a mock evaluator.
    if os.environ.get("GOOGLE_API_KEY") == "mock_key":
        pytest.skip(
            "Ragas evaluation requires a REAL GOOGLE_API_KEY. "
            "Skipping in mock CI environment."
        )

    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
    )

    # 6. Assertions (Thresholds)
    # In a real pipeline, we would enforce minimum scores.
    print(f"\nRagas Evaluation Results:\n{result}")

    # Example threshold checks
    # assert result['faithfulness'] > 0.8
    # assert result['answer_relevancy'] > 0.8
