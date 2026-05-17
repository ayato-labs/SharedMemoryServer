import abc
import asyncio

import httpx
from loguru import logger

from ripen.common.config import settings
from ripen.core.ai_control import AIRateLimiter, retry_on_ai_quota


class LlmProvider(abc.ABC):
    """Base class for LLM providers."""

    @abc.abstractmethod
    async def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
        """Generates text content based on the prompt."""
        pass

    @abc.abstractmethod
    async def check_health(self) -> bool:
        """Checks if the provider is correctly configured and reachable."""
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
                logger.debug(
                    f"Model metadata cached for {model_name}: {self._model_metadata[model_name]}"
                )
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

    @retry_on_ai_quota(max_retries=3, rotate_models=True, pool_name="compression")
    async def _compress_content(self, content: str, target_tokens: int) -> str:
        """
        Compresses/Distills the content using an LLM to fit within target_tokens.
        Uses the 'compression' model pool.
        """
        client = self._get_client()
        # In settings.py, generative_model returns model_manager.get_current_model()
        # which defaults to 'generation' pool. We need to manually pick from
        # the compression pool here.
        from ripen.core.ai_control import model_manager

        model = model_manager.get_current_model(pool_name="compression")

        logger.info(
            f"Triggering context compression using model: {model} (Target: {target_tokens} tokens)"
        )

        system_instruction = (
            "You are a high-precision data distillation engine. "
            "Your goal is to compress the provided text by removing redundant modifiers, "
            "connectives, and fillers, while preserving 100% of the core facts "
            "and logical relationships. "
            f"Aim to reduce the token count to approximately {target_tokens} tokens. "
            "Output ONLY the distilled facts, preferably as a dense list."
        )

        full_prompt = f"DISTILL THE FOLLOWING KNOWLEDGE:\n\n{content}"

        try:
            # We use the same throttle for compression to be safe
            await AIRateLimiter.throttle(task_type="generation")
            response = await client.aio.models.generate_content(
                model=model, contents=full_prompt, config={"system_instruction": system_instruction}
            )
            compressed_text = response.text
            new_tokens = await self._count_tokens(model, compressed_text)
            logger.info(f"Compression complete. Tokens reduced to {new_tokens}.")
            return compressed_text
        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            # If compression fails, we return the original and let the main flow handle the error
            return content

    @retry_on_ai_quota(max_retries=3, rotate_models=True, pool_name="generation")
    async def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Gemini API key not found.")

        # Main generation model
        model = settings.generative_model
        metadata = await self._get_model_metadata(model)

        # Combine system instruction with prompt for Gemini if provided
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"SYSTEM: {system_instruction}\n\nUSER: {prompt}"

        # Token management
        token_count = await self._count_tokens(model, full_prompt)
        limit = metadata["input_token_limit"]

        # Threshold for compression (90% of limit)
        safe_threshold = int(limit * 0.9)

        if token_count > safe_threshold:
            logger.warning(
                f"Token count ({token_count}) exceeds safe threshold ({safe_threshold}). "
                "Initiating autonomous compression..."
            )
            # We compress the USER prompt part primarily, as system instructions are usually static
            compressed_prompt = await self._compress_content(prompt, safe_threshold // 2)

            # Re-construct full prompt
            if system_instruction:
                full_prompt = f"SYSTEM: {system_instruction}\n\nUSER: {compressed_prompt}"
            else:
                full_prompt = compressed_prompt

            # Final check
            token_count = await self._count_tokens(model, full_prompt)
            logger.info(f"Post-compression token count: {token_count}")

        logger.info(f"Gemini API Request - Model: {model}, Tokens: {token_count}/{limit}")

        await AIRateLimiter.throttle(task_type="generation")

        try:
            # Add explicit timeout to prevent indefinite hangs on network/API issues
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=full_prompt),
                timeout=120.0
            )
            logger.info(f"Gemini response received. Model: {model}")
            return response.text
        except TimeoutError as e:
            logger.error(f"Gemini API call TIMEOUT (120s) - Model: {model}")
            raise Exception("AI Brain response timed out. Please try again.") from e
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    async def check_health(self) -> bool:
        """Checks if Gemini is configured and model exists."""
        try:
            client = self._get_client()
            if not client:
                return False
            
            # Check if model exists
            model_name = settings.generative_model
            try:
                # client.models.list is synchronous in google-genai
                models = client.models.list()
                model_names = [m.name for m in models]
                if model_name not in model_names and f"models/{model_name}" not in model_names:
                    logger.warning(
                        f"Configured Gemini model '{model_name}' might not be available. "
                        f"Available models: {model_names}"
                    )
            except Exception as e:
                logger.warning(f"Could not verify Gemini model existence: {e}")
                
            return True
        except Exception as e:
            logger.debug(f"Gemini health check failed: {e}")
            return False


class OllamaProvider(LlmProvider):
    """Ollama local provider (OpenAI-compatible API)."""

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.generative_model
        logger.debug(f"OllamaProvider initialized with model: {self.model}")

    async def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
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

    async def check_health(self) -> bool:
        """Checks if Ollama is reachable and model exists."""
        url = f"{self.base_url}/api/tags"
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    model_names = [m.get("name") for m in models]
                    
                    if self.model not in model_names:
                        has_match = False
                        for name in model_names:
                            if name.startswith(self.model) or self.model.startswith(name):
                                has_match = True
                                break
                        
                        if not has_match:
                            logger.warning(
                                f"Configured Ollama model '{self.model}' "
                                f"not found in installed models: {model_names}"
                            )
                    
                    return True
                return False
            except Exception as e:
                logger.debug(f"Ollama health check failed: {e}")
                return False


def get_llm_provider() -> LlmProvider:
    """Factory function to get the configured LLM provider."""
    provider_name = settings.llm_provider
    logger.debug(f"Creating LLM provider: {provider_name}")
    if provider_name == "gemini":
        return GeminiProvider()
    return OllamaProvider()
