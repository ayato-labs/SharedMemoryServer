import json
import os

from google import genai

from shared_memory.embeddings import _find_key_recursive


def verify():
    print("--- API Key Verification ---")

    # 1. Path check
    path = os.path.expanduser("~/.gemini/settings.json")
    print(f"Checking path: {path}")

    if not os.path.exists(path):
        print("CRITICAL: settings.json not found.")
        return

    # 2. Extract key exactly like our algorithm does
    try:
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)

            # Target path check
            env_config = settings.get("mcpServers", {}).get("SharedMemoryServer", {}).get("env", {})
            api_key = env_config.get("GOOGLE_API_KEY")
            source = "mcpServers.SharedMemoryServer.env.GOOGLE_API_KEY"

            if not api_key:
                api_key = _find_key_recursive(settings, "GOOGLE_API_KEY")
                source = "Recursive Search"

            if api_key:
                masked_key = f"{api_key[:4]}...{api_key[-4:]}"
                print(f"Found Key: {masked_key}")
                print(f"Source: {source}")
            else:
                print("No key found in settings.json")
                return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # 3. Direct API Call
    print("\n--- Requesting Google AI API ---")
    try:
        client = genai.Client(api_key=api_key)
        # Try to get basic model info (minimum tokens)
        model = client.models.get(model="gemini-1.5-flash")
        print(f"SUCCESS: Model '{model.name}' is accessible.")
        print("Status: API Key is ACTIVE and VALID.")
    except Exception as e:
        print("FAILURE: API Call failed.")
        print(f"Error Message: {e}")

        # Check if 'expired' or 'invalid' is in the error
        error_str = str(e).lower()
        if "expired" in error_str:
            print("\nRESULT: The API key is officially EXPIRED according to Google.")
        elif "invalid" in error_str:
            print("\nRESULT: The API key is INVALID (check for typos).")
        else:
            print("\nRESULT: Other error occurred (Network or Permission).")


if __name__ == "__main__":
    verify()
