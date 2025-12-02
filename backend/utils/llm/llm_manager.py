import asyncio
from typing import Optional

from . import llm_gemini


class LLMManager:
    """Generic LLM manager that controls concurrency for LLM calls.

    Responsibilities:
    - maintain an asyncio.Semaphore sized by the configured concurrency limit
    - delegate actual LLM calls to an injected client (default: gemini_client)
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
        self.client = client or llm_gemini.gemini_client

    @classmethod
    def from_simulation_config(cls, simulation_config: dict, client: Optional[object] = None):
        """Create an LLMManager from a simulation config dict (expects key `llm_concurrency_limit`)."""
        # Use direct indexing to ensure callers supply validated configs (no fallback)
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
