"""
eval_benchmark.py
Public benchmark reproduction script.
"""

import time
import torch
from unsloth import FastLanguageModel

MODEL_ID = "Ilieg/qwen2.5-7b-phishing-standard-merged-16bit"

def main():
    print(f"[*] Loading model {MODEL_ID} in 4-bit quantized mode...")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_ID,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    peak_vram = torch.cuda.max_memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0
    print(f"✅ Peak VRAM Allocation: {peak_vram:.2f} GB")

    prompt = "**URGENT**: Verify your bank account immediately."
    messages = [{"role": "user", "content": f"Classify this email:\n{prompt}"}]
    
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")

    start = time.perf_counter()
    _ = model.generate(input_ids=inputs, max_new_tokens=256, do_sample=False)
    latency_ms = (time.perf_counter() - start) * 1000

    print(f"✅ Inference Latency: {latency_ms:.2f} ms")

if __name__ == "__main__":
    main()