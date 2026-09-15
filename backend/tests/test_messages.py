import pytest
from pydantic import ValidationError

from app.schemas.messages import (
    ClientMessage,
    ConversationAnalysisUpdate,
    ErrorMessage,
    EventMessage,
    RiskUpdate,
    TranscriptUpdate,
    VoiceAnalysisUpdate,
)


def test_client_message_valid():
    msg = ClientMessage(type="ping", data={})
    assert msg.type == "ping"


def test_client_message_requires_type():
    with pytest.raises(ValidationError):
        ClientMessage(data={})


def test_voice_analysis_valid():
    msg = VoiceAnalysisUpdate(score=88.0, is_spoof=True, confidence="Spoof Detected",
                              raw_bonafide_logit=-2.1)
    assert msg.type == "voice_analysis"
    assert msg.score == 88.0


def test_voice_analysis_accepts_suspicious_status():
    msg = VoiceAnalysisUpdate(
        score=55.0, is_spoof=False, confidence="Spoof Signals Confirming",
        status="suspicious", raw_bonafide_logit=-1.2,
    )
    assert msg.status == "suspicious"


def test_voice_analysis_rejects_unknown_status():
    with pytest.raises(ValidationError):
        VoiceAnalysisUpdate(score=50.0, is_spoof=False, confidence="x",
                            status="maybe_human", raw_bonafide_logit=0.0)


def test_set_language_control_message_shape():
    msg = ClientMessage(type="set_language", data={"language": "hi"})
    assert msg.data["language"] == "hi"


def test_voice_analysis_score_out_of_range():
    with pytest.raises(ValidationError):
        VoiceAnalysisUpdate(score=150.0, is_spoof=True, confidence="x",
                            raw_bonafide_logit=0.0)


def test_conversation_analysis_valid():
    msg = ConversationAnalysisUpdate(
        urgency=0.9, authority_impersonation=0.5, financial_request=0.0,
        credential_request=0.0, otp_request=0.1, threat=0.2,
        secrecy=0.7, persuasion=0.6, repeated_confirmation=0.8,
        confidence=0.7, reasons=["urgency pressure", "don't discuss"],
    )
    assert 0.0 <= msg.urgency <= 1.0
    assert msg.secrecy == 0.7
    assert msg.persuasion == 0.6
    assert msg.repeated_confirmation == 0.8
    assert msg.type == "conversation_analysis"


def test_conversation_analysis_defaults():
    msg = ConversationAnalysisUpdate()
    assert msg.urgency == 0.0
    assert msg.reasons == []


def test_risk_update_valid():
    msg = RiskUpdate(risk_score=87, risk_level="CRITICAL", voice_score=35.0,
                     social_score=32.0, action_score=20.0,
                     reasons=["a", "b"], recommendation="Do not comply")
    assert msg.risk_level == "CRITICAL"


def test_risk_update_invalid_level():
    with pytest.raises(ValidationError):
        RiskUpdate(risk_score=50, risk_level="SUPER", voice_score=0.0,
                   social_score=0.0, action_score=0.0)


def test_risk_update_score_out_of_range():
    with pytest.raises(ValidationError):
        RiskUpdate(risk_score=101, risk_level="CRITICAL", voice_score=0.0,
                   social_score=0.0, action_score=0.0)


def test_event_message_valid():
    msg = EventMessage(id="e1", timestamp="00:02", message="hello",
                       severity="warning", source="voice")
    assert msg.type == "event"


def test_event_message_rejects_bad_source():
    with pytest.raises(ValidationError):
        EventMessage(id="e1", timestamp="00:02", message="h",
                     severity="warning", source="alien")


def test_error_message_valid():
    msg = ErrorMessage(message="oops", code="INFERENCE_ERROR")
    assert msg.type == "error"


def test_transcript_message_defaults_speaker_caller():
    msg = TranscriptUpdate(id="t1", timestamp="00:00", text="hi")
    assert msg.speaker == "caller"
    assert msg.type == "transcript"