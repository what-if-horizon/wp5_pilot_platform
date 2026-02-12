import os
import asyncio
from anthropic import Anthropic, AsyncAnthropic
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class AnthropicClient:
    """Client for interacting with the Anthropic API (sync + async)."""

    def __init__(self, model_name: str = "claude-sonnet-4-5", temperature: float = None):
        self.model_name = model_name
        self.temperature = temperature
        api_key = os.getenv("ANTHROPIC_API_KEY")

        # Create sync client
        self.client = Anthropic(api_key=api_key)

        # Create async client
        try:
            self.aclient = AsyncAnthropic(api_key=api_key)
        except Exception:
            self.aclient = None

    def generate_response(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Synchronous response generation."""
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                kwargs = dict(
                    model=self.model_name,
                    max_tokens=1024,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                )
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                message = self.client.messages.create(**kwargs)
                return message.content[0].text

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Async response generation using the async Anthropic client when available."""
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                if self.aclient is not None:
                    kwargs = dict(
                        model=self.model_name,
                        max_tokens=1024,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                    )
                    if self.temperature is not None:
                        kwargs["temperature"] = self.temperature
                    message = await self.aclient.messages.create(**kwargs)
                    return message.content[0].text
                else:
                    # Fallback: run sync client in executor
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(
                        None, lambda: self.generate_response(prompt, max_retries=0)
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
