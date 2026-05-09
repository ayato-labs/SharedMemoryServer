import sys
from pathlib import Path

from google import genai

from shared_memory.common.config import settings

# Add src to sys.path
src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)


def check_model_metadata():
    api_key = settings.api_key
    if not api_key:
        print("API Key not found in settings.")
        return

    client = genai.Client(api_key=api_key)
    
    # Try to list models
    try:
        print("Listing models...")
        # Note: In google-genai, listing models might require different method or parameters
        # based on the documentation for the 'google-genai' (Vertex AI / Google AI SDK)
        # For Google AI (Generative AI SDK), it is often client.models.list()
        
        models = client.models.list()
        for m in models:
            # We look for input_token_limit or context_window equivalent
            # The structure of Model object in google-genai includes:
            # name, version, display_name, description, input_token_limit, 
            # output_token_limit, supported_generation_methods
            print(f"Model: {m.name}")
            print(f"  Display Name: {m.display_name}")
            print(f"  Input Token Limit: {getattr(m, 'input_token_limit', 'N/A')}")
            print(f"  Output Token Limit: {getattr(m, 'output_token_limit', 'N/A')}")
            print("-" * 20)

    except Exception as e:
        print(f"Error listing models: {e}")

    # Try to get a specific model's metadata
    target_model = "gemini-1.5-flash"
    try:
        print(f"\nGetting metadata for {target_model}...")
        m = client.models.get(model=target_model)
        print(f"Name: {m.name}")
        print(f"Input token limit: {m.input_token_limit}")
        print(f"Output token limit: {m.output_token_limit}")
    except Exception as e:
        print(f"Error getting {target_model} metadata: {e}")

if __name__ == "__main__":
    check_model_metadata()
