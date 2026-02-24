import os
import asyncio
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

BASE_URL = "https://whatif.inf.uni-konstanz.de/v1"


class KonstanzClient:
    """Client for the University of Konstanz vLLM endpoint (OpenAI-compatible)."""

    def __init__(self, model_name: str = "BSC-LT/ALIA-40b", temperature: float = None):
        self.model_name = model_name
        self.temperature = temperature
        api_key = os.getenv("KONSTANZ_API_KEY", "")

        self.client = OpenAI(base_url=BASE_URL, api_key=api_key)

        try:
            self.aclient = AsyncOpenAI(base_url=BASE_URL, api_key=api_key)
        except Exception:
            self.aclient = None

    def generate_response(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Synchronous response generation."""
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
        """Async response generation using the async OpenAI client when available."""
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
                    completion = await self.aclient.chat.completions.create(**kwargs)
                    return completion.choices[0].message.content
                else:
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
