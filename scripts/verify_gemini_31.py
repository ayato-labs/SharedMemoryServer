import os
import json
from google import genai
from shared_memory.embeddings import _find_key_recursive

def verify():
    print("--- API Key Verification (Strict Model Check) ---")
    
    path = os.path.expanduser("~/.gemini/settings.json")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Targeting exactly what you pointed out
            env_config = settings.get("mcpServers", {}).get("SharedMemoryServer", {}).get("env", {})
            api_key = env_config.get("GOOGLE_API_KEY")
            
            if api_key:
                masked_key = f"{api_key[:4]}...{api_key[-4:]}"
                print(f"Using Key from settings.json: {masked_key}")
            else:
                print("No key found at mcpServers.SharedMemoryServer.env.GOOGLE_API_KEY")
                return
    except Exception as e:
        print(f"Error reading settings.json: {e}")
        return

    # Requesting EXACTLY the model you specified
    target_model = "gemini-3.1-flash-lite-preview"
    print(f"\n--- Requesting Google AI API with model: {target_model} ---")
    
    try:
        client = genai.Client(api_key=api_key)
        # Minimum request to verify key and model access
        response = client.models.generate_content(
            model=target_model,
            contents="Confirming API Key Status. Reply with 'OK' if you see this."
        )
        print(f"SUCCESS! Gemini responded: {response.text.strip()}")
        print(f"RESULT: The API Key and model '{target_model}' are FULLY OPERATIONAL.")
    except Exception as e:
        print(f"FAILURE: API Call failed.")
        error_msg = str(e)
        print(f"Raw Error from Google: {error_msg}")
        
        if "expired" in error_msg.lower():
            print("\nRESULT: Official Google Response -> API Key is EXPIRED.")
        elif "not found" in error_msg.lower():
            print(f"\nRESULT: Official Google Response -> Model '{target_model}' not found for this key/region.")
        else:
            print("\nRESULT: Access denied or other configuration issue.")

if __name__ == "__main__":
    verify()
