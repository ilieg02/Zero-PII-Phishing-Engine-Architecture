"""
schemas/contracts.py

Public API Contracts for the Zero-PII Gateway.
Defines the strict Pydantic v2 schemas used for fast JSON validation 
and vLLM xgrammar constrained decoding.
"""

from pydantic import BaseModel, Field, field_validator
import re
import hashlib

class EmailAnalysisRequest(BaseModel):
    """Contract for inbound requests from the enterprise gateway."""
    email_text: str = Field(
        ..., 
        min_length=10, 
        max_length=8192,
        description="Raw email body text. Fails fast if under 10 chars to prevent DoS."
    )
    mode: str = Field(
        default="fast", 
        pattern="^(fast|think)$",
        description="Execution mode: 'fast' (256 tokens) or 'think' (512 tokens)"
    )

class ThreatAnalysisDetail(BaseModel):
    """The deeply nested analysis struct enforced by the LLM."""
    risk_score: int = Field(..., ge=0, le=100, description="0 (Safe) to 100 (Critical)")
    risk_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    classification: str = Field(..., pattern="^(phishing|benign)$")
    signals: list[str] = Field(..., description="List of detected social engineering tactics")
    explanation: str = Field(..., max_length=512)
    recommended_action: str = Field(..., max_length=256)

class ThreatAnalysisResponse(BaseModel):
    """Final outbound payload matching SIEM/SOAR ingestion requirements."""
    status: str = Field(default="success", pattern="^(success|error)$")
    mode_used: str = Field(..., pattern="^(fast|think|cpu_fallback)$")
    safe_log_hash: str = Field(..., description="SHA-256 hash for secure database auditing")
    analysis: ThreatAnalysisDetail

    @field_validator("safe_log_hash")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("Audit log hash must be a valid SHA-256 string.")
        return v