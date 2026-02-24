import asyncio
from datetime import datetime
from typing import Optional


class SalamandraClient:
    """Client for local inference with BSC Salamandra instruct models.

    Loads the model and tokenizer once at init, then runs generation
    on the local GPU/CPU for each request.  The model uses a ChatML
    chat template with a date_string parameter.
    """

    def __init__(
        self,
        model_name: str = "BSC-LT/salamandra-7b-instruct",
        temperature: float = None,
        max_new_tokens: int = 256,
    ):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        self.model_name = model_name
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Select device and dtype based on available hardware:
        #   CUDA  → device_map="auto" (accelerate) + bfloat16
        #   MPS   → explicit device placement + float16 (bfloat16 support is patchy)
        #   CPU   → float32 (no half-precision benefit without accelerator)
        if torch.cuda.is_available():
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                dtype=torch.bfloat16,
            )
        elif torch.backends.mps.is_available():
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.float16,
            ).to("mps")
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.float32,
            )

    def generate_response(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Synchronous response generation via local model."""
        import torch

        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                # When a separate system_prompt is provided, use it in the
                # system role and the prompt as the user message.  Otherwise
                # fall back to the legacy layout where the entire prompt goes
                # into the system slot with a short Spanish trigger as user.
                if system_prompt is not None:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ]
                else:
                    messages = [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": "Genera el mensaje de chat ahora."},
                    ]
                date_string = datetime.today().strftime("%Y-%m-%d")

                templated = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    date_string=date_string,
                )

                encoded = self.tokenizer(
                    templated, add_special_tokens=False, return_tensors="pt"
                )
                input_ids = encoded["input_ids"].to(self.model.device)
                attention_mask = encoded["attention_mask"].to(self.model.device)
                input_len = input_ids.shape[-1]

                gen_kwargs = dict(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=self.max_new_tokens,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
                if self.temperature is not None and self.temperature > 0:
                    gen_kwargs["do_sample"] = True
                    gen_kwargs["temperature"] = self.temperature
                else:
                    gen_kwargs["do_sample"] = False

                with torch.no_grad():
                    output_ids = self.model.generate(**gen_kwargs)

                # Decode only the newly generated tokens
                new_tokens = output_ids[0][input_len:]
                return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

            except Exception as e:
                last_error = str(e)
                attempts += 1

                if attempts > max_retries:
                    print(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
                    return None

        return None

    async def generate_response_async(self, prompt: str, max_retries: int = 1, system_prompt: str = None) -> Optional[str]:
        """Async wrapper — runs the blocking generate in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_response(prompt, max_retries=max_retries, system_prompt=system_prompt)
        )

    def close(self) -> None:
        """Release model from memory."""
        try:
            del self.model
            del self.tokenizer
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass

    async def aclose(self) -> None:
        """Async close — delegates to sync close."""
        self.close()
