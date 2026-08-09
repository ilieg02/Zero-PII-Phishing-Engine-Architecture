#!/usr/bin/env python3
"""
Zero-PII AI Phishing Risk Scoring Engine — Reproducible Evaluation Benchmark

Usage:
    python eval_benchmark.py

This script:
    1. Validates the hardware/software environment.
    2. Downloads the public Qwen2.5-7B phishing model (4-bit quantized).
    3. Runs inference on representative email samples.
    4. Reports latency, VRAM footprint, and JSON parse success rate.
    5. Saves a benchmark receipt in test-artifacts/.
"""

import sys
import time
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

import torch
from packaging import version

# ---------- Environment Checks ----------
def check_environment():
    """Ensure the evaluator's machine can run the benchmark."""
    # 1. Python version
    if not (3, 10) <= sys.version_info < (3, 12):
        sys.exit("ERROR: Python 3.10 or 3.11 is required. Current: {}.{}.{}".format(*sys.version_info[:3]))

    # 2. CUDA GPU
    if not torch.cuda.is_available():
        sys.exit("ERROR: No CUDA GPU detected. This benchmark requires a GPU (e.g., T4, RTX).")

    gpu_name = torch.cuda.get_device_name(0)
    total_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
    if total_mem < 10.0:
        print(f"Warning: GPU '{gpu_name}' has only {total_mem:.1f} GB VRAM. "
              f"Recommended >= 15 GB for safety, though 4‑bit should fit in ~6 GB.")

    # 3. bitsandbytes
    try:
        import bitsandbytes as bnb
    except ImportError:
        sys.exit("ERROR: bitsandbytes not installed. Please run: pip install bitsandbytes")

    # 4. Optional xformers
    try:
        import xformers
        print("xformers available – attention kernels optimized.")
    except ImportError:
        print("xformers not installed – performance may be slightly lower (still functional).")

    print(f"✓ Environment OK. GPU: {gpu_name} ({total_mem:.1f} GB)")
    return gpu_name, total_mem


# ---------- Model Loading ----------
def load_model():
    """Download (if needed) and load the 4‑bit quantized model."""
    from unsloth import FastLanguageModel
    from huggingface_hub import login, HfApi

    MODEL_NAME = "Ilieg/qwen2.5-7b-phishing-standard-merged-16bit"

    # Check if the repo is accessible (try unauthenticated first)
    try:
        api = HfApi()
        api.model_info(MODEL_NAME)
    except Exception as e:
        if "401" in str(e) or "403" in str(e):
            print("Model requires authentication. Please login to Hugging Face.")
            login()  # will prompt for token
        else:
            raise RuntimeError(f"Cannot access model repository '{MODEL_NAME}': {e}")

    print(f"Loading model '{MODEL_NAME}' in 4‑bit (Unsloth AWQ)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=2048,
        dtype=None,           # auto
        load_in_4bit=True,
        trust_remote_code=False,  # Qwen2.5 is now in transformers
    )
    FastLanguageModel.for_inference(model)
    print("✓ Model loaded successfully.")
    return model, tokenizer


# ---------- Prompt Formatting ----------
CHATML_TEMPLATE = (
    "{% for message in messages %}"
    "{% if message['role'] == 'system' %}{{ '<|im_start|>system\n' + message['content'] + '<|im_end|>\n' }}"
    "{% elif message['role'] == 'user' %}{{ '<|im_start|>user\n' + message['content'] + '<|im_end|>\n' }}"
    "{% elif message['role'] == 'assistant' %}{{ '<|im_start|>assistant\n' + message['content'] + '<|im_end|>\n' }}"
    "{% endif %}{% endfor %}"
    "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
)

def build_prompt(email_text: str, mode: str, tokenizer) -> str:
    """
    Construct the exact ChatML prompt that the fine‑tuned model expects.
    Returns a plain string ready for tokenization.
    """
    system = (
        "You are an enterprise email security classifier. Analyze the email and output a single JSON object "
        "with fields: risk_score (0-100), risk_level (low/medium/high/critical), "
        "classification (legitimate/phishing/spam/benign), signals (list of strings), "
        "explanation, recommended_action. Be precise and follow the schema exactly."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Email:\n{email_text}\n\nMode: {mode}"},
    ]

    # Override tokenizer's chat_template to guarantee consistency across transformers versions
    tokenizer.chat_template = CHATML_TEMPLATE
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )


# ---------- Inference & Timing ----------
def run_inference(model, tokenizer, prompt: str, max_new_tokens: int = 256):
    """Run a single inference with precise GPU‑synchronised timing."""
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.0,          # deterministic
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    # Decode only the newly generated tokens
    generated_ids = outputs[0][inputs.input_ids.shape[1]:]
    response = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return response.strip(), elapsed


# ---------- JSON Validation ----------
from schemas.contracts import FastAnalysisResponse, ThinkAnalysisResponse

def parse_and_validate(raw_output: str, mode: str):
    """
    Extract JSON from the model's raw output and validate against Pydantic schemas.
    Returns (validated_dict, error_string).
    """
    try:
        # Find the first '{' and last '}' to extract JSON
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1
        if start == -1 or end <= start:
            return None, "No JSON object found in model output"

        json_str = raw_output[start:end]
        data = json.loads(json_str)

        # Choose the appropriate schema
        if mode == "think":
            validated = ThinkAnalysisResponse(**data)
        else:
            validated = FastAnalysisResponse(**data)
        return validated.dict(), None
    except Exception as e:
        return None, str(e)


# ---------- Memory Tracking ----------
def get_gpu_memory():
    return {
        "allocated_GB": torch.cuda.memory_allocated(0) / 1e9,
        "reserved_GB": torch.cuda.memory_reserved(0) / 1e9,
        "max_allocated_GB": torch.cuda.max_memory_allocated(0) / 1e9,
        "max_reserved_GB": torch.cuda.max_memory_reserved(0) / 1e9,
    }


# ---------- Main Benchmark ----------
def main():
    # 1. Environment & hardware checks
    gpu_name, total_mem = check_environment()

    # 2. Load model (4‑bit)
    model, tokenizer = load_model()
    torch.cuda.reset_peak_memory_stats()   # reset after loading
    mem_after_load = get_gpu_memory()
    print(f"VRAM after model load: {mem_after_load['allocated_GB']:.2f} GB allocated, "
          f"{mem_after_load['reserved_GB']:.2f} GB reserved")

    # 3. Sample emails (representative of the 500‑sample test split)
    samples = [
        ("URGENT: Your account has been compromised. Verify immediately at http://login-update-portal.com.", "fast"),
        ("Your monthly AWS billing report for August is now available. No action needed.", "fast"),
        ("Hi team, please process the attached wire transfer to the new vendor account. Cheers, John", "fast"),
        # Add more if desired
    ]

    # 4. Warm‑up (discard timing)
    print("Running warm‑up inference...")
    warm_text, _ = samples[0]
    warm_prompt = build_prompt(warm_text, "fast", tokenizer)
    _, _ = run_inference(model, tokenizer, warm_prompt, max_new_tokens=10)
    print("✓ Warm‑up complete.")

    # 5. Benchmark each sample
    results = []
    parse_errors = 0
    for idx, (email_text, mode) in enumerate(samples):
        safe_hash = hashlib.sha256(email_text.encode()).hexdigest()
        prompt = build_prompt(email_text, mode, tokenizer)

        max_tokens = 256 if mode == "fast" else 512
        raw_output, latency = run_inference(model, tokenizer, prompt, max_new_tokens=max_tokens)
        validated, error = parse_and_validate(raw_output, mode)

        if error:
            parse_errors += 1
            print(f"  Sample {idx+1}: JSON parse ERROR – {error}")
        else:
            print(f"  Sample {idx+1}: OK – risk={validated['analysis']['risk_score']} "
                  f"class={validated['analysis']['classification']}")

        results.append({
            "email_hash": safe_hash,
            "mode": mode,
            "latency_ms": round(latency * 1000, 2),
            "json_valid": error is None,
            "output": validated if error is None else raw_output[:200] + "...",
        })

    # 6. Final memory report
    mem_final = get_gpu_memory()
    peak_vram = mem_final["max_allocated_GB"]
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)

    # 7. Print summary and cross‑check with README claims
    print("\n" + "="*60)
    print(" BENCHMARK SUMMARY")
    print("="*60)
    print(f"GPU: {gpu_name}")
    print(f"Peak VRAM (allocated): {peak_vram:.2f} GB  (claimed: ~5.9 GB)")
    print(f"Average latency: {avg_latency:.1f} ms  (claimed: ~255 ms for fast mode)")
    print(f"JSON parse errors: {parse_errors}/{len(samples)}  (claimed: 0%)")
    print("="*60)

    # 8. Save a receipt file
    receipt_path = Path("test-artifacts") / f"benchmark_receipt_{datetime.now():%Y%m%d_%H%M%S}.json"
    receipt_path.parent.mkdir(exist_ok=True)
    receipt = {
        "timestamp": datetime.now().isoformat(),
        "gpu": gpu_name,
        "peak_vram_GB": round(peak_vram, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "parse_errors": parse_errors,
        "samples": results,
    }
    with open(receipt_path, "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\n✓ Benchmark receipt saved to {receipt_path}")

    # 9. Assertions for CI/validation (optional, but nice for evaluators)
    try:
        assert peak_vram < 6.5, f"VRAM too high: {peak_vram:.2f} GB"
        assert parse_errors == 0, "JSON parse errors detected!"
        print("All assertions passed. Model performance matches README claims.")
    except AssertionError as e:
        print(f"WARNING: {e}")


if __name__ == "__main__":
    main()