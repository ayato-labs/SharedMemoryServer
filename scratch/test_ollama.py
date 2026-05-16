import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, "C:/Users/saiha/My_Service/programing/MCP/Ripen/Ripen-free/src")

# Set environment variables to override config
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL"] = "gemma4:e2b"

from ripen.infra.llm import get_llm_provider

async def test_ollama():
    print("Initializing Ollama provider with model gemma4:e2b...")
    provider = get_llm_provider()
    
    print("Checking health (is Ollama running?)...")
    is_healthy = await provider.check_health()
    print(f"Health Check: {is_healthy}")
    
    if not is_healthy:
        print("Ollama is not reachable. Please make sure 'ollama serve' is running.")
        return
        
    print("\nAttempting to generate content...")
    try:
        response = await provider.generate_content("こんにちは。あなたは誰ですか？簡潔に答えてください。")
        print("Response received:")
        print(response)
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())
