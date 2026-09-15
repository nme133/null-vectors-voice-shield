from app.api.websocket import SessionState, _merge_conversation_evidence


def _analysis(**overrides):
    base = {
        "urgency": 0.6, "financial_request": 0.7, "secrecy": 0.8,
        "confidence": 0.7, "reasons": ["confirm the transfer"],
    }
    base.update(overrides)
    return base


def test_merge_accumulates_evidence():
    state = SessionState()
    _merge_conversation_evidence(state, _analysis())
    assert state.conversation_signals["financial_request"] == 0.7
    assert state.conversation_signals["secrecy"] == 0.8
    assert state.conversation_signals["reasons"] == ["confirm the transfer"]


def test_merge_weak_or_empty_analysis_cannot_zero_strong_signals():
    # The core regression: a later transcript that produces a weak/empty GPT
    # result must NOT overwrite already-detected strong evidence with 0.
    state = SessionState()
    _merge_conversation_evidence(state, _analysis())  # strong first
    _merge_conversation_evidence(state, {})           # empty analysis
    _merge_conversation_evidence(state, {"urgency": 0.2})  # weak partial
    cur = state.conversation_signals
    assert cur["financial_request"] == 0.7
    assert cur["secrecy"] == 0.8
    assert cur["reasons"] == ["confirm the transfer"]


def test_merge_new_strong_evidence_raises_value():
    state = SessionState()
    _merge_conversation_evidence(state, {"financial_request": 0.4})
    _merge_conversation_evidence(state, {"financial_request": 0.9, "threat": 0.6})
    assert state.conversation_signals["financial_request"] == 0.9
    assert state.conversation_signals["threat"] == 0.6


def test_merge_deduplicates_reasons():
    state = SessionState()
    _merge_conversation_evidence(state, {"reasons": ["urgent", "don't discuss"]})
    _merge_conversation_evidence(state, {"reasons": ["urgent", "trust me"]})
    reasons = state.conversation_signals["reasons"]
    assert reasons == ["urgent", "don't discuss", "trust me"]


def test_merge_rejects_non_numeric_fields():
    state = SessionState()
    _merge_conversation_evidence(state, {"urgency": "garbage", "secrecy": None})
    assert state.conversation_signals["urgency"] == 0.0
    assert state.conversation_signals["secrecy"] == 0.0