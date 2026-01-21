import os
import asyncio
from huggingface_hub import InferenceClient, AsyncInferenceClient
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class HuggingFaceClient:
    """Client for interacting with HuggingFace Inference API (sync + async)."""

    def __init__(self, model_name: str = "meta-llama/Llama-3.1-8B-Instruct:novita"):
        """
        Initialize HuggingFace client. Creates both a sync client and an async client.
        """
        self.model_name = model_name
        api_key = os.getenv("HF_API_KEY")

        # Create sync client
        self.client = InferenceClient(api_key=api_key)

        # Create async client
        try:
            self.aclient = AsyncInferenceClient(api_key=api_key)
        except Exception:
            self.aclient = None

    def generate_response(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Synchronous response generation.

        This method is kept for backward compatibility.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )
                return completion.choices[0].message.content

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1) -> Optional[str]:
        """Async response generation using the async HuggingFace client when available.

        Falls back to running the sync client in a threadpool if the async client is
        not available.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                if self.aclient is not None:
                    completion = await self.aclient.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                    )
                    return completion.choices[0].message.content
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


# Global instance for easy import
huggingface_client = HuggingFaceClient()
