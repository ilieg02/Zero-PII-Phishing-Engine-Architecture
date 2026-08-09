# 🛡️ Enterprise AI Threat Engine: Zero-PII Phishing Risk Scoring Service

<p align="center">
  <img src="banner-bw.svg" alt="System Banner" width="100%" />
</p>

<p align="center">
  <a href="https://huggingface.co/Ilieg/qwen2.5-7b-phishing-standard-merged-16bit">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Fine--Tuned%20Model-ffc107?style=for-the-badge" alt="Hugging Face Model">
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg?style=for-the-badge" alt="License: GPL-3.0">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/vLLM-High%20Throughput-722ed1?style=for-the-badge" alt="vLLM Serving">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic v2">
</p>

An enterprise-grade, privacy-preserving email threat scoring engine powered by a fine-tuned **Qwen2.5-7B** model. Served via high-throughput **vLLM** with logits-level grammar enforcement (**XGrammar**), zero-PII header sanitization, and fallback orchestration.

> **Public Architecture Specification:** This repository contains the public system design documentation, API contracts (`schemas/contracts.py`), and a reproducible evaluation benchmark harness (`eval_benchmark.py`). The proprietary API gateway routing, production deployment configurations, and internal security rules are maintained in a private enterprise repository.

---

## 🎨 System Overview & Defensive AI Engineering

Standard commercial LLM endpoints introduce severe enterprise risks: **PII data leakage** across network boundaries and **JSON schema parsing failures** caused by non-deterministic model outputs. This architecture addresses both challenges:

- **Zero-PII Ingestion Pipeline:** Incoming email headers, origin IPs, authentication tokens, and user identities are cryptographically anonymized via SHA-256 or stripped prior to GPU tensor allocation.
- **Comprehensive QLoRA Adapter Tuning:** By expanding QLoRA target adapters beyond standard attention modules (`q, k, v, o`) to include MLP projections (`gate_proj`, `up_proj`, `down_proj`), the engine captures subtle social engineering, authority manipulation, and zero-link BEC lures.
- **Logits-Level Grammar Enforcement:** Leverages vLLM's `xgrammar` engine coupled with Pydantic v2 schemas to construct finite-state machine (FSM) masks, guaranteeing **0% schema parsing errors** at the token generation level.
- **Dynamic Mode Execution:**
  - **Perimeter Scan (`fast` mode):** 256 token max generation target (~255 ms latency) for real-time gateway routing.
  - **Deep SOC Analysis (`think` mode):** 512 token max generation target with structured reasoning traces for security analyst review.

---

## 📊 Evaluation & Benchmark Results

Evaluated on a held-out, deduplicated unseen test split ($N = 500$ emails) consisting of real-world corporate communications, spear-phishing lures, and false-positive traps:

| Model Variant | Tuned Target Modules | Accuracy | Phishing F1-Score | ROC-AUC | Avg. Latency | VRAM Footprint |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen2.5-7B (Base Zero-Shot)** | None | 82.40% | 80.10% | 0.8310 | ~240 ms | 14.2 GB (16-bit) |
| **Standard LoRA** | `q, k, v, o` | 97.00% | 96.50% | 0.9681 | ~250 ms | 5.8 GB (4-bit AWQ) |
| **Comprehensive LoRA (Ours - Best)** | `q, k, v, o, gate, up, down` | **97.80%** | **97.46%** | **0.9773** | ~255 ms | 5.9 GB (4-bit AWQ) |

### Key Capabilities
- **Zero-Link BEC Detection:** Identifies payroll routing diversions, vendor bank details changes, and urgent executive gift-card lures lacking links or attachments.
- **Low False-Positive Rate:** Distinguishes legitimate MFA reset codes, AWS billing threshold alerts, Okta lockouts, and bug bounty reports from malicious lures.
- **Structured Output Ready:** Trained on ChatML format for seamless integration with vLLM guided decoding (xgrammar/Pydantic v2).

### Key Engineering Takeaway
> While attention-only LoRA captures surface-level keyword indicators, expanding trainable parameters to MLP projections (gate_proj, up_proj, down_proj) allows the model to learn complex semantic reasoning patterns (e.g., implicit urgency manipulation and brand impersonation), boosting Phishing F1-Score by **+0.96%** with negligible latency overhead (+5 ms).

**Note on Storage vs. Runtime VRAM:** The weights published on Hugging Face are merged 16-bit bfloat16 files (15.2 GB on disk). When loaded for serving via 4-bit AWQ/Unsloth quantization, active runtime GPU memory consumption drops to **~5.9 GB VRAM**, enabling deployment on cost-effective enterprise GPUs (e.g., RTX 4070 / L4).

---

## 🔌 API Contract Specifications

The API accepts structured JSON requests and returns deterministic threat verdicts validated by Pydantic v2.

**Standard Phishing Request (fast mode)**

- {
  "email_text": "URGENT: Your account has been compromised. Verify immediately at http://login-update-portal.com.",
  "mode": "fast"} 


## Validated Threat Verdict Response (200 OK)

- {
  "status": "success",
  "mode_used": "fast",
  "safe_log_hash": "7776d3645028f2e975522eb8d551f2c4239565dc7482bafd246439942a23722a",
  "analysis": {
    "risk_score": 85,
    "risk_level": "high",
    "classification": "phishing",
    "signals": [
      "Artificial urgency tactics",
      "Suspicious account verification link"
    ],
    "explanation": "Email contains threat patterns indicating automated phishing.",
    "recommended_action": "Do not click links. Report to security team."
  }}

## 🛠️ Reproducing the Benchmark

- A standalone, robust evaluation script is provided to independently verify memory footprint, inference latency, and JSON schema compliance using the public Hugging Face weights.

## Hardware Requirements

   - NVIDIA GPU with at least 10 GB VRAM (16 GB recommended). Tested on T4, RTX 4070, L4.

    Python 3.10 or 3.11 (3.12 not yet fully supported by Unsloth).

    CUDA toolkit compatible with your PyTorch installation (typically included in Colab or pre‑installed in Docker images).

## Quick Start (Local)


# 1. Clone the repository
- git clone https://github.com/ilieg02/Zero-PII-Phishing-Engine-Architecture.git
- cd Zero-PII-Phishing-Engine-Architecture

# 2. Create and activate a virtual environment (Python 3.10)
- python3.10 -m venv .venv
- source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the benchmark
python eval_benchmark.py

- The script will:

    Verify the GPU and Python environment.

    Download the 4‑bit quantized model from Hugging Face.

    Run inference on representative phishing/legitimate samples.

    Print latency, peak VRAM, and JSON parse success rate.

    Save a detailed receipt to test-artifacts/benchmark_receipt_*.json.

- Docker (Zero Environment Hassle)

docker build -t zero-pii-benchmark .
docker run --gpus all -it zero-pii-benchmark

> A pre‑built Docker image is available on Docker Hub (coming soon).
📁 Repository Structure
text

├── schemas/
│   └── contracts.py          # Pydantic v2 API contracts
├── test-artifacts/           # Benchmark receipts (generated at runtime)
├── eval_benchmark.py         # Main evaluation harness
├── requirements.txt          # Pinned Python dependencies
├── README.md                 # This document
└── LICENSE                   # GPL-3.0

    Note: The test-artifacts/ directory contains runtime‑generated benchmark receipts only. No static GPU logs are provided, as the script dynamically creates its own proof.

## 📜 License

> This public repository is licensed under the GNU General Public License v3.0. The model weights on Hugging Face are also released under GPL-3.0.
🤝 Contact & Internship Inquiries

If you're a recruiter, security architect, or fellow engineer interested in this project, feel free to connect with me on LinkedIn or open a discussion in this repository.

Built with precision by Ilie Gabuja. Protecting inboxes, one inference at a time.