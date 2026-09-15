from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Client → Server
# ---------------------------------------------------------------------------

class ClientMessage(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Server → Client
# ---------------------------------------------------------------------------

class VoiceAnalysisUpdate(BaseModel):
    type: Literal["voice_analysis"] = "voice_analysis"
    score: float = Field(..., ge=0.0, le=100.0, description="Spoof score 0-100 (higher = more spoof)")
    is_spoof: bool
    confidence: str
    status: Literal["spoof", "suspicious", "bona_fide", "insufficient_speech"] = "bona_fide"
    model: str = "Spectra-AASIST3"
    raw_bonafide_logit: float = Field(..., description="Raw model logit for bona-fide class")


class TranscriptUpdate(BaseModel):
    type: Literal["transcript"] = "transcript"
    id: str
    timestamp: str
    speaker: Literal["caller"] = "caller"
    text: str


class ConversationAnalysisUpdate(BaseModel):
    type: Literal["conversation_analysis"] = "conversation_analysis"
    urgency: float = Field(0.0, ge=0.0, le=1.0)
    authority_impersonation: float = Field(0.0, ge=0.0, le=1.0)
    financial_request: float = Field(0.0, ge=0.0, le=1.0)
    credential_request: float = Field(0.0, ge=0.0, le=1.0)
    otp_request: float = Field(0.0, ge=0.0, le=1.0)
    threat: float = Field(0.0, ge=0.0, le=1.0)
    secrecy: float = Field(0.0, ge=0.0, le=1.0)
    persuasion: float = Field(0.0, ge=0.0, le=1.0)
    repeated_confirmation: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class RiskUpdate(BaseModel):
    type: Literal["risk_update"] = "risk_update"
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    voice_score: float = Field(..., description="Voice contribution to risk (0-40)")
    social_score: float = Field(..., description="Social engineering contribution (0-40)")
    action_score: float = Field(..., description="High-risk action contribution (0-20)")
    reasons: list[str] = Field(default_factory=list)
    recommendation: str = ""


class EventMessage(BaseModel):
    type: Literal["event"] = "event"
    id: str
    timestamp: str
    message: str
    severity: Literal["info", "warning", "critical", "success"]
    source: Literal["audio", "voice", "nlp", "engine"] = "engine"


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    message: str
    components: dict[str, str] = Field(default_factory=dict)


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: str = "UNKNOWN"


class ConnectedMessage(BaseModel):
    type: Literal["connected"] = "connected"
    message: str = "Session established"
    device: str = ""
    spectra_loaded: bool = False
    demo_mode: bool = False
