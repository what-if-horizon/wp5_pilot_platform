"""Quick smoke-test for SalamandraClient with step-by-step timing."""

import time

MODEL_ID = "BSC-LT/salamandra-2b-instruct"
TEST_PROMPT = (
    "Eres un participante amigable en un chat en línea sobre el cambio climático. "
    "Escribe un mensaje corto e informal compartiendo tu opinión sobre las energías renovables."
)


def main():
    # ── 1. Import ────────────────────────────────────────────────
    t0 = time.perf_counter()
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    t_import = time.perf_counter() - t0
    print(f"[1] Import torch + transformers:  {t_import:.2f}s")

    # ── 2. Load tokenizer ────────────────────────────────────────
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    t_tokenizer = time.perf_counter() - t0
    print(f"[2] Load tokenizer:              {t_tokenizer:.2f}s")

    # ── 3. Load model ────────────────────────────────────────────
    t0 = time.perf_counter()
    if torch.cuda.is_available():
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, device_map="auto", dtype=torch.bfloat16,
        )
    elif torch.backends.mps.is_available():
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, dtype=torch.float16,
        ).to("mps")
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, dtype=torch.float32,
        )
    t_model = time.perf_counter() - t0
    device = next(model.parameters()).device
    print(f"[3] Load model ({device}):  {t_model:.2f}s")

    # ── 4. Tokenize + apply chat template ────────────────────────
    from datetime import datetime

    t0 = time.perf_counter()
    messages = [{"role": "user", "content": TEST_PROMPT}]
    date_string = datetime.today().strftime("%Y-%m-%d")

    templated = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        date_string=date_string,
    )
    encoded = tokenizer(templated, add_special_tokens=False, return_tensors="pt")
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded["attention_mask"].to(device)
    input_len = input_ids.shape[-1]
    t_tokenize = time.perf_counter() - t0
    print(f"[4] Tokenize ({input_len} tokens):       {t_tokenize:.4f}s")

    # ── 5. Generate ──────────────────────────────────────────────
    t0 = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id,
        )
    t_generate = time.perf_counter() - t0
    new_tokens = output_ids[0][input_len:]
    n_generated = len(new_tokens)
    tokens_per_sec = n_generated / t_generate if t_generate > 0 else 0
    print(f"[5] Generate ({n_generated} tokens):     {t_generate:.2f}s  ({tokens_per_sec:.1f} tok/s)")

    # ── 6. Decode ────────────────────────────────────────────────
    t0 = time.perf_counter()
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    t_decode = time.perf_counter() - t0
    print(f"[6] Decode:                      {t_decode:.4f}s")

    # ── Summary ──────────────────────────────────────────────────
    total = t_import + t_tokenizer + t_model + t_tokenize + t_generate + t_decode
    print(f"\n{'='*55}")
    print(f"Total:                           {total:.2f}s")
    print(f"  Startup (import+load):         {t_import + t_tokenizer + t_model:.2f}s")
    print(f"  Inference (tok+gen+dec):        {t_tokenize + t_generate + t_decode:.2f}s")
    print(f"\n--- Response ---\n{response}")


if __name__ == "__main__":
    main()
