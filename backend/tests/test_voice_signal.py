import pytest

from app.api.websocket import SessionState, _update_voice_signal, _vote_streak

# Raw bona-fide logit test points around the Spectra threshold (-1.0625).
AI_LOGIT = -3.0    # below threshold -> spoof vote
HUMAN_LOGIT = 1.0  # at/above threshold -> bona-fide vote


def test_vote_streak_consecutive_never_walks_back():
    # A maxed spoof streak (+5) must restart at -1 on the first bona-fide
    # vote — NOT traverse +5 -> +4 -> ... -> -5 over nine windows.  That
    # walk-back is what made the meter cling to RED after switching to a
    # real human voice.
    assert _vote_streak(5, False) == -1
    assert _vote_streak(-1, False) == -2
    assert _vote_streak(-5, True) == 1
    assert _vote_streak(1, True) == 2
    assert _vote_streak(2, True) == 3


def test_vote_streak_clamps():
    assert _vote_streak(5, True) == 5
    assert _vote_streak(-5, False) == -5


def test_ai_verdict_confirms_after_three_windows():
    # Conservative: three consecutive below-threshold windows required before
    # committing to a spoof verdict.
    state = SessionState()
    _update_voice_signal(state, AI_LOGIT)
    assert state.voice_signal["is_spoof"] is False
    assert state.voice_signal["status"] == "suspicious"
    _update_voice_signal(state, AI_LOGIT)
    assert state.voice_signal["is_spoof"] is False
    assert state.voice_signal["status"] == "suspicious"
    _update_voice_signal(state, AI_LOGIT)
    assert state.voice_signal["is_spoof"] is True
    assert state.voice_signal["status"] == "spoof"


def test_switching_to_human_clears_within_three_windows():
    state = SessionState()
    for _ in range(5):
        _update_voice_signal(state, AI_LOGIT)
    assert state.voice_signal["status"] == "spoof"

    # One human window: verdict holds (small temporal persistence), but the
    # three-way status degrades to suspicious instead of staying RED.
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["is_spoof"] is True
    assert state.voice_signal["status"] == "suspicious"

    # Two consecutive human windows: still not cleared (needs three for the
    # conservative bona-fide commit).
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["is_spoof"] is True
    assert state.voice_signal["status"] == "suspicious"

    # Three consecutive human windows: clears to bona_fide (green).
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["is_spoof"] is False
    assert state.voice_signal["status"] == "bona_fide"


def test_single_noisy_spoof_window_does_not_flip_human():
    state = SessionState()
    for _ in range(3):
        _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["status"] == "bona_fide"

    # One noisy below-threshold window must NOT flip a human verdict — it only
    # moves the evidence to "suspicious".
    _update_voice_signal(state, AI_LOGIT)
    assert state.voice_signal["is_spoof"] is False
    assert state.voice_signal["status"] == "suspicious"

    # Three consecutive human windows restore the bona-fide verdict.
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["is_spoof"] is False
    assert state.voice_signal["status"] == "suspicious"
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["status"] == "suspicious"
    _update_voice_signal(state, HUMAN_LOGIT)
    assert state.voice_signal["status"] == "bona_fide"


def test_display_score_still_tracks_smoothed_logit():
    idx = pytest.importorskip("app.api.websocket")
    from app.api.websocket import _score_to_display

    ai_score = _score_to_display(-3.0)
    human_score = _score_to_display(1.0)
    assert ai_score > human_score
    assert 0.0 <= human_score <= 100.0


def test_display_score_anchored_at_threshold():
    # The displayed index is anchored to the model's own bona-fide threshold:
    # at the threshold it reads 50 (neutral), strong spoofs read near 96,
    # clearly-human logits read near 4.  It is a signal-strength index, not a
    # probability.
    idx = pytest.importorskip("app.api.websocket")
    from app.api.websocket import _score_to_display

    assert abs(_score_to_display(-1.0625009) - 50.0) < 0.001
    assert _score_to_display(-5.0) >= 90.0
    assert _score_to_display(4.0) <= 5.0