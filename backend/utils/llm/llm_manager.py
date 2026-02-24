import asyncio
from typing import Optional


def _create_client(provider: str, model: str = None, temperature: float = None, top_p: float = None):
    """Create an LLM client for the given provider and optional model name.

    Imports are done lazily so only the selected provider's package needs to be installed.
    """
    provider = (provider or "gemini").lower()

    kwargs = {}
    if model:
        kwargs["model_name"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature

    if provider == "huggingface":
        from .provider.llm_huggingface import HuggingFaceClient
        return HuggingFaceClient(**kwargs)
    elif provider == "gemini":
        from .provider.llm_gemini import GeminiClient
        return GeminiClient(**kwargs)
    elif provider == "anthropic":
        from .provider.llm_anthropic import AnthropicClient
        return AnthropicClient(**kwargs)
    elif provider == "mistral":
        from .provider.llm_mistral import MistralClient
        if top_p is not None:
            kwargs["top_p"] = top_p
        return MistralClient(**kwargs)
    elif provider == "konstanz":
        from .provider.llm_konstanz import KonstanzClient
        return KonstanzClient(**kwargs)
    elif provider == "none":
        from .local.llm_salamandra import SalamandraClient
        return SalamandraClient(**kwargs)
    else:
        raise RuntimeError(f"Unknown llm_provider: '{provider}'. Supported: 'gemini', 'huggingface', 'anthropic', 'mistral', 'konstanz', 'None' (local)")


def _create_client_from_config(simulation_config: dict):
    """Create the appropriate LLM client based on simulation config.

    Supports both legacy keys (llm_provider/llm_model) and the new
    role-prefixed keys (performer_llm_provider, director_llm_provider).
    When called without a role prefix this returns the Performer client.
    """
    provider = simulation_config.get("llm_provider", "gemini")
    model = simulation_config.get("llm_model")
    return _create_client(provider, model)


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
    def from_simulation_config(cls, simulation_config: dict, client: Optional[object] = None, role: str = None):
        """Create an LLMManager from a simulation config dict.

        When `role` is provided (e.g. "director" or "performer"), the factory
        looks for role-prefixed keys like `director_llm_provider` / `director_llm_model`.
        Falls back to the generic `llm_provider` / `llm_model` keys.
        """
        if client is None:
            if role:
                provider = simulation_config.get(f"{role}_llm_provider")
                model = simulation_config.get(f"{role}_llm_model")
                temperature = simulation_config.get(f"{role}_temperature")
                top_p = simulation_config.get(f"{role}_top_p")
                if provider:
                    client = _create_client(provider, model, temperature=temperature, top_p=top_p)
            if client is None:
                client = _create_client_from_config(simulation_config)
        return cls(simulation_config["llm_concurrency_limit"], client=client)

    async def generate_response(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Acquire concurrency slot and delegate to the LLM client's async generator.

        Returns the response text or None on failure.
        """
        async with self._semaphore:
            # The underlying client is expected to implement async method
            # `generate_response_async(prompt, max_retries, system_prompt)` returning Optional[str].
            try:
                # type: ignore[attr-defined]
                return await self.client.generate_response_async(prompt, max_retries=max_retries, system_prompt=system_prompt)
            except AttributeError:
                # Fallback: maybe client only exposes sync API
                # run the sync call in a threadpool
                import asyncio as _asyncio

                loop = _asyncio.get_running_loop()
                return await loop.run_in_executor(None, lambda: self.client.generate_response(prompt, max_retries=max_retries, system_prompt=system_prompt))
            except Exception:
                return None


__all__ = ["LLMManager"]
