import os
import asyncio
from mistralai import Mistral
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class MistralClient:
    """Client for interacting with the Mistral API (sync + async)."""

    def __init__(self, model_name: str = "mistral-large-latest", temperature: float = None, top_p: float = None):
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        api_key = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=api_key)

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
                    safe_prompt=False,
                )
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                if self.top_p is not None:
                    kwargs["top_p"] = self.top_p
                response = self.client.chat.complete(**kwargs)
                return response.choices[0].message.content

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Async response generation using the Mistral async methods."""
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
                    safe_prompt=False,
                )
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                if self.top_p is not None:
                    kwargs["top_p"] = self.top_p
                response = await self.client.chat.complete_async(**kwargs)
                return response.choices[0].message.content

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"Async LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def aclose(self) -> None:
        """Close the async client if present."""
        try:
            await self.client.close()
        except Exception:
            pass

    def close(self) -> None:
        """Close the sync client."""
        try:
            self.client.close()
        except Exception:
            pass
