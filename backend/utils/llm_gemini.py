import os
import asyncio
from google import genai
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class GeminiClient:
    """Client for interacting with Google Gemini API (sync + async helpers)."""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize Gemini client. Creates both a sync client and an async wrapper (.aio).
        """
        self.model_name = model_name
        # create sync client (underlying genai Client)
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        # async client wrapper (per genai docs)
        try:
            # .aio attribute provides async client
            self.aclient = self.client.aio
        except Exception:
            # If for some reason aio is not available, set to None and callers should
            # fall back to run_in_executor.
            self.aclient = None

    def generate_response(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Synchronous response generation (existing behavior).

        This method is kept for backward compatibility.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Async response generation using the async genai client when available.

        Falls back to running the sync client in a threadpool if the async client is
        not available.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                if self.aclient is not None:
                    resp = await self.aclient.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    )
                    return getattr(resp, "text", None)
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
                await self.aclient.aclose()
            except Exception:
                pass

    def close(self) -> None:
        """Close the sync client."""
        try:
            self.client.close()
        except Exception:
            pass


# Global instance for easy import
gemini_client = GeminiClient()