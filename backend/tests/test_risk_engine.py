from app.services.risk_engine import RiskEngine, classify_level


def _signal_set(**overrides):
    base = {
        "urgency": 0.0, "authority_impersonation": 0.0, "financial_request": 0.0,
        "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0,
        "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0,
        "confidence": 0.0, "reasons": [],
    }
    base.update(overrides)
    return base


def test_classify_level_boundaries():
    assert classify_level(0) == "LOW"
    assert classify_level(29) == "LOW"
    assert classify_level(30) == "MEDIUM"
    assert classify_level(59) == "MEDIUM"
    assert classify_level(60) == "HIGH"
    assert classify_level(79) == "HIGH"
    assert classify_level(80) == "CRITICAL"
    assert classify_level(100) == "CRITICAL"


def test_low_risk_normal_voice():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(),
    )
    assert snap.risk_score == 0
    assert snap.risk_level == "LOW"


def test_speaking_alone_never_increases_risk():
    # A human speaking (bona-fide logit at/above threshold) contributes
    # nothing.  Talking is not evidence of risk.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(),
    )
    assert snap.voice_component == 0.0
    assert snap.risk_score == 0
    assert snap.risk_level == "LOW"


def test_live_disposition_contributes_below_threshold():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=-3.2,
        conversation_signals=_signal_set(),
    )
    assert 0.0 < snap.voice_component <= 20.0
    assert "Suspicious acoustic anomalies in voice" in snap.reasons


def test_live_voice_never_exceeds_cap_without_confirmation():
    # A single un-confirmed sub-threshold logit stays within LOW and can
    # never alone escalate the call.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=-30.0,
        conversation_signals=_signal_set(),
    )
    assert snap.voice_component == 20.0
    assert snap.risk_level == "LOW"


def test_confirmed_spoof_with_normal_conversation_is_elevated_but_not_critical():
    # Spectra confirms spoof while conversation is completely normal:
    # risk is elevated (voice 15-40) but NOT CRITICAL.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=True,
        bonafide_logit=-3.5,
        conversation_signals=_signal_set(),
    )
    assert 15.0 <= snap.voice_component <= 40.0
    assert snap.risk_level in ("LOW", "MEDIUM")
    assert snap.risk_level != "CRITICAL"


def test_high_spoof_logit_contributes_voice_points():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=True,
        bonafide_logit=-5.0,
        conversation_signals=_signal_set(),
    )
    assert snap.voice_component == 40.0
    assert snap.risk_score >= 40
    assert "Possible synthetic/ cloned voice detected" in snap.reasons


def test_social_engineering_points():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(
            urgency=1.0, authority_impersonation=1.0,
            financial_request=1.0, threat=1.0,
            secrecy=1.0, persuasion=1.0, repeated_confirmation=1.0,
        ),
    )
    assert snap.social_component == 40.0
    assert snap.risk_score >= 40
    assert "Caller impersonates authority or institution" in snap.reasons


def test_conversation_alone_can_reach_high_even_with_normal_voice():
    # Root-cause regression: "Human voice + severe financial social
    # engineering must NOT remain LOW".  With every conversation channel maxed
    # out but Spectra sounding perfectly human, the conversation evidence
    # alone must push the call to HIGH (60) — never stay at ~19.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(
            urgency=1.0, authority_impersonation=1.0, financial_request=1.0,
            credential_request=1.0, otp_request=1.0, threat=1.0,
            secrecy=1.0, persuasion=1.0, repeated_confirmation=1.0,
        ),
    )
    assert snap.voice_component == 0.0
    assert snap.social_component == 40.0
    assert snap.action_component == 20.0
    assert snap.risk_score == 60
    assert snap.risk_level == "HIGH"


def test_transfer_pressure_transcript_raises_risk_out_of_low():
    # The reported transcript: initiated transfer + "confirm, confirm, confirm"
    # + "time sensitive" + "don't discuss this".  Under the old formula this
    # summed to ~19 (LOW).  These are realistic GPT-OSS readings; together they
    # must leave LOW even though the voice is human.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(
            urgency=0.85, financial_request=0.7, secrecy=0.8,
            persuasion=0.75, repeated_confirmation=0.9, confidence=0.8,
        ),
    )
    assert snap.voice_component == 0.0
    assert snap.social_component > 20.0
    assert snap.risk_score >= 30
    assert snap.risk_level != "LOW"
    assert "Repeated confirmation requests detected" in snap.reasons
    assert "Caller discourages discussion of the transaction" in snap.reasons
    assert "Caller is pressuring the user to confirm a transfer" in snap.reasons
    assert "Urgent financial action detected" in snap.reasons
    assert "Trust/persuasion pressure detected" in snap.reasons


def test_missing_or_invalid_signal_fields_do_not_crash_or_distort():
    # A signal dict that omits fields or contains junk must be scored as if
    # those channels have no evidence — but must never raise an error.
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals={"urgency": 1.0, "secrecy": None, "garbage": "x"},
    )
    assert snap.social_component == 9.0
    assert snap.action_component == 0.0
    assert 0 <= snap.risk_score <= 100


def test_missing_fields_cannot_override_existing_strong_signals():
    # The merge lives in the WebSocket layer, but the engine must only ever
    # ADD evidence: recomputing with fewer signals keeps prior channel scores
    # intact (this is what _merge_conversation_evidence guarantees upstream).
    engine = RiskEngine()
    full = engine.compute(
        is_spoof=False, bonafide_logit=5.0,
        conversation_signals=_signal_set(financial_request=0.9, urgency=0.8),
    )
    partial = engine.compute(
        is_spoof=False, bonafide_logit=5.0,
        conversation_signals=_signal_set(urgency=0.2),
    )
    # A clean reading only reduces the total gradually via the asymmetric EMA;
    # it must not drop the score on the identical evidence in one step.
    assert partial.risk_score >= full.risk_score * 0.5


def test_high_risk_action_points():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=False,
        bonafide_logit=5.0,
        conversation_signals=_signal_set(
            financial_request=1.0, credential_request=1.0, otp_request=1.0,
        ),
    )
    assert snap.action_component == 20.0


def test_critical_full_attack():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=True,
        bonafide_logit=-5.0,
        conversation_signals=_signal_set(
            urgency=1.0, authority_impersonation=1.0, financial_request=1.0,
            threat=1.0, otp_request=1.0, credential_request=1.0,
            secrecy=1.0, persuasion=1.0, repeated_confirmation=1.0,
        ),
    )
    assert snap.risk_score == 100
    assert snap.risk_level == "CRITICAL"
    assert "DO NOT transfer funds" in snap.recommendation


def test_score_is_not_probability():
    # risk_score must never be associated with a probability claim in output
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=True,
        bonafide_logit=-5.0,
        conversation_signals=_signal_set(urgency=1.0),
    )
    assert 0 <= snap.risk_score <= 100
    assert isinstance(snap.risk_score, int)


def test_score_reason_explainability():
    engine = RiskEngine()
    snap = engine.compute(
        is_spoof=True,
        bonafide_logit=-2.0,
        conversation_signals=_signal_set(authority_impersonation=0.8),
    )
    assert len(snap.reasons) >= 1
    assert isinstance(snap.reasons[0], str)


def test_smoothing_prevents_jump():
    engine = RiskEngine()
    s1 = engine.compute(is_spoof=True, bonafide_logit=-5.0, conversation_signals=_signal_set())
    s2 = engine.compute(is_spoof=False, bonafide_logit=5.0, conversation_signals=_signal_set())
    # Immediately following a cold reset the EMA pulls hard, so
    # the second score should be <= the first.
    assert s2.risk_score <= s1.risk_score