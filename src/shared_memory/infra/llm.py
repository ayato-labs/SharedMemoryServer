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

    @retry_on_ai_quota(max_retries=3, rotate_models=True)
    async def generate_content(self, prompt: str, system_instruction: str = None) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Gemini API key not found.")

        logger.debug(
            f"Gemini generate_content start. Instruction len: {len(system_instruction or '')}"
        )
        await AIRateLimiter.throttle(task_type="generation")

        # Combine system instruction with prompt for Gemini if provided
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"SYSTEM: {system_instruction}\n\nUSER: {prompt}"

        model = settings.generative_model
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
