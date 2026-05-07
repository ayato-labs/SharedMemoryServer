import abc

import httpx
from loguru import logger

from shared_memory.common.config import settings
from shared_memory.core.ai_control import AIRateLimiter, retry_on_ai_quota


class LlmProvider(abc.ABC):
    """Base class for LLM providers."""

    @abc.abstractmethod
    async def generate_content(self, prompt: str, system_instruction: str = None) -> str:
        """Generates text content based on the prompt."""
        pass


class GeminiProvider(LlmProvider):
    """Gemini API provider."""

    def __init__(self):
        self._client = None
        self._model_metadata = {}

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai

                api_key = settings.api_key
                if not api_key:
                    logger.warning("Gemini API key not found in settings.")
                    return None
                self._client = genai.Client(api_key=api_key)
                logger.debug("Gemini client initialized.")
            except ImportError:
                logger.error("google-genai not installed. Please install it to use Gemini.")
                raise
        return self._client

    async def _get_model_metadata(self, model_name: str):
        """Fetches and caches model metadata."""
        if model_name not in self._model_metadata:
            client = self._get_client()
            try:
                # Meta-data retrieval is synchronous in google-genai Client.models.get
                meta = client.models.get(model=model_name)
                self._model_metadata[model_name] = {
                    "input_token_limit": meta.input_token_limit,
                    "output_token_limit": meta.output_token_limit,
                }
                logger.debug(f"Model metadata cached for {model_name}: {self._model_metadata[model_name]}")
            except Exception as e:
                logger.warning(f"Failed to fetch metadata for {model_name}: {e}")
                # Fallback to conservative defaults if metadata fetch fails
                self._model_metadata[model_name] = {
                    "input_token_limit": 32768,
                    "output_token_limit": 4096,
                }
        return self._model_metadata[model_name]

    async def _count_tokens(self, model_name: str, contents: str) -> int:
        """Counts tokens for the given contents."""
        client = self._get_client()
        try:
            # count_tokens is synchronous in google-genai Client.models.count_tokens
            resp = client.models.count_tokens(model=model_name, contents=contents)
            return resp.total_tokens
        except Exception as e:
            logger.warning(f"Token counting failed for {model_name}: {e}")
            # Fallback to character-based estimation (1 token ~ 4 chars)
            return len(contents) // 4

    @retry_on_ai_quota(max_retries=3, rotate_models=True)
    async def generate_content(self, prompt: str, system_instruction: str = None) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Gemini API key not found.")

        model = settings.generative_model
        metadata = await self._get_model_metadata(model)
        
        # Combine system instruction with prompt for Gemini if provided
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"SYSTEM: {system_instruction}\n\nUSER: {prompt}"

        # Token management
        token_count = await self._count_tokens(model, full_prompt)
        limit = metadata["input_token_limit"]
        
        logger.info(
            f"Gemini API Request - Model: {model}, Tokens: {token_count}/{limit}"
        )

        if token_count > limit * 0.9:
            logger.warning(
                f"Token count ({token_count}) is approaching or exceeding limit ({limit}). "
                "Truncation or chunking may be required."
            )
            # Future Improvement: Implement dynamic chunking/truncation here
            # For now, we proceed but log the risk.
            if token_count > limit:
                logger.error("Token count strictly exceeds model limit. This call will likely fail.")

        await AIRateLimiter.throttle(task_type="generation")

        try:
            response = await client.aio.models.generate_content(model=model, contents=full_prompt)
            logger.info(f"Gemini response received. Model: {model}")
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise


class OllamaProvider(LlmProvider):
    """Ollama local provider (OpenAI-compatible API)."""

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.generative_model
        logger.debug(f"OllamaProvider initialized with model: {self.model}")

    async def generate_content(self, prompt: str, system_instruction: str = None) -> str:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_instruction:
            payload["system"] = system_instruction

        logger.debug(f"Ollama generate_content start. Model: {self.model}")
        await AIRateLimiter.throttle(task_type="generation")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 404:
                    msg = (
                        f"Ollama model '{self.model}' not found. "
                        "Please run 'ollama pull' or check README.md for setup."
                    )
                    logger.error(msg)
                    raise RuntimeError(msg)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Ollama response received. Model: {self.model}")
                return data.get("response", "")
            except httpx.ConnectError as e:
                msg = "Could not connect to Ollama. Is it running? (Check 'ollama serve')"
                logger.error(msg)
                raise RuntimeError(msg) from e
            except Exception as e:
                logger.error(f"Ollama call failed: {e}")
                raise RuntimeError(f"Ollama provider error: {e}") from e


def get_llm_provider() -> LlmProvider:
    """Factory function to get the configured LLM provider."""
    provider_name = settings.llm_provider
    logger.debug(f"Creating LLM provider: {provider_name}")
    if provider_name == "gemini":
        return GeminiProvider()
    return OllamaProvider()
