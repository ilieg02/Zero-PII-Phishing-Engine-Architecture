"""
Enterprise Email Threat Scoring API Contracts (Pydantic v2)

These schemas enforce deterministic, machine‑readable responses
for both fast perimeter scans and deep SOC analysis.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class FastAnalysisResult(BaseModel):
    risk_score: int = Field(..., ge=0, le=100, description="0-100 risk score")
    risk_level: Literal["low", "medium", "high", "critical"]
    classification: Literal["legitimate", "phishing", "spam", "benign"]
    signals: List[str] = Field(default_factory=list,
        description="Concise list of detected threat indicators")
    explanation: str = Field(..., description="Brief reasoning summary")
    recommended_action: str = Field(..., description="Actionable mitigation step")

class FastAnalysisResponse(BaseModel):
    status: Literal["success", "error"]
    mode_used: Literal["fast"] = "fast"
    safe_log_hash: str = Field(..., description="SHA‑256 hash of the original email content (PII‑safe)")
    analysis: FastAnalysisResult

class ThinkAnalysisResult(FastAnalysisResult):
    reasoning_trace: str = Field(..., description="Detailed step‑by‑step analysis logic for SOC review")
    confidence_breakdown: Optional[dict] = Field(None, description="Per‑signal confidence scores")

class ThinkAnalysisResponse(BaseModel):
    status: Literal["success", "error"]
    mode_used: Literal["think"] = "think"
    safe_log_hash: str
    analysis: ThinkAnalysisResult