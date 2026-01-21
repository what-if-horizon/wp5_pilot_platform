import asyncio
from typing import Optional

from .llm_gemini import GeminiClient
from .llm_huggingface import HuggingFaceClient


def _create_client_from_config(simulation_config: dict):
    """Create the appropriate LLM client based on simulation config."""
    provider = simulation_config.get("llm_provider", "gemini").lower()
    model = simulation_config.get("llm_model")

    if provider == "huggingface":
        if model:
            return HuggingFaceClient(model_name=model)
        return HuggingFaceClient()
    elif provider == "gemini":
        if model:
            return GeminiClient(model_name=model)
        return GeminiClient()
    else:
        raise RuntimeError(f"Unknown llm_provider: '{provider}'. Supported: 'gemini', 'huggingface'")


class LLMManager:
    """Generic LLM manager that controls concurrency for LLM calls.

    Responsibilities:
    - maintain an asyncio.Semaphore sized by the configured concurrency limit
    - delegate actual LLM calls to an injected client (selected based on config)
    """

    def __init__(self, concurrency_limit: int, client: Optional[object] = None):
        if concurrency_limit is None:
            raise RuntimeError("llm_concurrency_limit must be provided")
        try:
            limit = int(concurrency_limit)
        except Exception:
            raise RuntimeError("llm_concurrency_limit must be an integer")
        if limit <= 0:
            raise RuntimeError("llm_concurrency_limit must be a positive integer (>0)")

        self._semaphore = asyncio.Semaphore(limit)
        # LLM client should provide `generate_response_async(prompt, max_retries)`
        self.client = client

    @classmethod
    def from_simulation_config(cls, simulation_config: dict, client: Optional[object] = None):
        """Create an LLMManager from a simulation config dict.

        Expects keys: `llm_concurrency_limit`, and optionally `llm_provider` and `llm_model`.
        If no client is provided, one is created based on `llm_provider` (default: gemini).
        """
        if client is None:
            client = _create_client_from_config(simulation_config)
        return cls(simulation_config["llm_concurrency_limit"], client=client)

    async def generate_response(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Acquire concurrency slot and delegate to the LLM client's async generator.

        Returns the response text or None on failure.
        """
        async with self._semaphore:
            # The underlying client is expected to implement async method
            # `generate_response_async(prompt, max_retries)` returning Optional[str].
            try:
                # type: ignore[attr-defined]
                return await self.client.generate_response_async(prompt, max_retries=max_retries)
            except AttributeError:
                # Fallback: maybe client only exposes sync API
                # run the sync call in a threadpool
                import asyncio as _asyncio

                loop = _asyncio.get_running_loop()
                return await loop.run_in_executor(None, lambda: self.client.generate_response(prompt, max_retries=max_retries))
            except Exception:
                return None


__all__ = ["LLMManager"]
