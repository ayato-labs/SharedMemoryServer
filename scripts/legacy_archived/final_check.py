import sys

try:
    print("Python path:", sys.path)
    from shared_memory.embeddings import get_gemini_client

    print("Import success!")

    client = get_gemini_client()
    if client:
        print("Gemini client initialized!")
        models = [m.name for m in client.models.list()]
        print("Available models (first 5):", models[:5])
    else:
        print("Gemini client FAILED to initialize (API key missing?)")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
