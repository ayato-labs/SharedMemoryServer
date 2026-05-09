import asyncio
import sys
from pathlib import Path

from google import genai

from shared_memory.common.config import settings

# Add src to sys.path
src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

async def verify_token_counting():
    api_key = settings.api_key
    if not api_key:
        print("API Key not found.")
        return

    client = genai.Client(api_key=api_key)
    model_id = settings.generative_model
    
    print(f"Testing with model: {model_id}")
    
    # Get metadata
    try:
        m = client.models.get(model=model_id)
        print(f"Input Token Limit: {m.input_token_limit}")
    except Exception as e:
        print(f"Error getting metadata: {e}")

    # Test count_tokens
    test_prompts = [
        "Hello world!",
        "A" * 1000,
        "SYSTEM: You are a helpful assistant.\n\nUSER: Tell me a long story about a cat."
    ]

    for p in test_prompts:
        try:
            # Check the method signature for count_tokens in google-genai
            # Usually: client.models.count_tokens(model=model_id, contents=contents)
            resp = client.models.count_tokens(model=model_id, contents=p)
            print(f"Prompt length: {len(p)} chars -> {resp.total_tokens} tokens")
        except Exception as e:
            print(f"Error counting tokens for '{p[:20]}...': {e}")

if __name__ == "__main__":
    asyncio.run(verify_token_counting())
