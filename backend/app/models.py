from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
Regulation = Literal["AI_ACT", "GDPR", "DSA", "UCPD"]


class CampaignSubmission(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20, max_length=60000)
    channels: list[str] = Field(default_factory=list)
    target_audience: Optional[str] = None
    markets: list[str] = Field(default_factory=list)
    uses_ai_generation: Optional[bool] = None
    uses_personalisation: Optional[bool] = None


class Finding(BaseModel):
    regulation: Regulation
    provision_id: str
    provision_ref: str
    title: str
    severity: Severity
    rationale: str
    evidence_quote: Optional[str] = None
    recommendation: str
    graph_path: list[str] = Field(default_factory=list)
    celex: Optional[str] = None
    source_url: Optional[str] = None


class TriageResult(BaseModel):
    detected_practices: list[str] = Field(default_factory=list)
    audience_notes: Optional[str] = None
    ai_involved: bool = False
    personal_data_involved: bool = False
    minors_potentially_reached: bool = False
    regulations_to_check: list[Regulation] = Field(default_factory=list)
    summary: str = ""


class RegulationVerdict(BaseModel):
    regulation: Regulation
    status: Literal["violation_likely", "risk_identified", "attention", "compliant", "not_applicable"]
    findings: list[Finding] = Field(default_factory=list)
    notes: str = ""


class AnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    campaign: CampaignSubmission
    triage: Optional[TriageResult] = None
    verdicts: list[RegulationVerdict] = Field(default_factory=list)
    overall_risk: Literal["critical", "high", "medium", "low", "compliant", "unknown"] = "unknown"
    executive_summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    engine: Literal["agentic", "heuristic"] = "agentic"
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    error: Optional[str] = None
