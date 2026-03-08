import os
import asyncio
from huggingface_hub import InferenceClient, AsyncInferenceClient
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class HuggingFaceClient:
    """Client for interacting with HuggingFace Inference API (sync + async)."""

    def __init__(self, model_name: str = "meta-llama/Llama-3.1-8B-Instruct:novita", temperature: float = None, top_p: float = None, max_tokens: int = 1024):
        """
        Initialize HuggingFace client. Creates both a sync client and an async client.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        api_key = os.getenv("HF_API_KEY")

        # Create sync client
        self.client = InferenceClient(api_key=api_key)

        # Create async client
        try:
            self.aclient = AsyncInferenceClient(api_key=api_key)
        except Exception:
            self.aclient = None

    def generate_response(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Synchronous response generation.

        This method is kept for backward compatibility.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                messages = []
                if system_prompt is not None:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                kwargs = dict(
                    model=self.model_name,
                    messages=messages,
                )
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                if self.top_p is not None:
                    kwargs["top_p"] = self.top_p
                kwargs["max_tokens"] = self.max_tokens
                completion = self.client.chat.completions.create(**kwargs)
                return completion.choices[0].message.content

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Async response generation using the async HuggingFace client when available.

        Falls back to running the sync client in a threadpool if the async client is
        not available.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                if self.aclient is not None:
                    messages = []
                    if system_prompt is not None:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    kwargs = dict(
                        model=self.model_name,
                        messages=messages,
                    )
                    if self.temperature is not None:
                        kwargs["temperature"] = self.temperature
                    if self.top_p is not None:
                        kwargs["top_p"] = self.top_p
                    kwargs["max_tokens"] = self.max_tokens
                    completion = await self.aclient.chat.completions.create(**kwargs)
                    return completion.choices[0].message.content
                else:
                    # Fallback: run sync client in executor
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(
                        None, lambda: self.generate_response(prompt, max_retries=0, system_prompt=system_prompt)
                    )
                    return resp

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"Async LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def aclose(self) -> None:
        """Close the async client if present."""
        if self.aclient is not None:
            try:
                await self.aclient.close()
            except Exception:
                pass

    def close(self) -> None:
        """Close the sync client."""
        try:
            self.client.close()
        except Exception:
            pass
