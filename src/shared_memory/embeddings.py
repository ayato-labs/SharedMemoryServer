import os
from google import genai
from .utils import log_error

EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONALITY = 768

def get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        log_error("Failed to initialize Google AI client", e)
        return None

async def compute_embedding(text: str):
    client = get_gemini_client()
    if not client:
        return None
    try:
        # google-genai client is blocking
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": DIMENSIONALITY}
        )
        return result.embeddings[0].values
    except Exception as e:
        log_error("Embedding computation failed", e)
        return None
