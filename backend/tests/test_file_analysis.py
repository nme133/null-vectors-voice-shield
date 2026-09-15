import asyncio
import io

import numpy as np
import pytest
import soundfile as sf

from app.services import file_analysis as famod
from app.services.file_analysis import aggregate_voice_results, plan_spectra_windows

THRESHOLD = -1.0625009


def _speech_samples(seconds: float, sr: int = 16000) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_plan_spectra_windows_short_file_single_window():
    audio = _speech_samples(2.0)  # < 64.6 k samples
    windows = plan_spectra_windows(audio)
    assert len(windows) == 1
    assert len(windows[0]) == len(audio)


def test_plan_spectra_windows_long_file_advances_by_hop():
    audio = _speech_samples(20.0, sr=16000)  # 320 k samples
    windows = plan_spectra_windows(audio, hop_samples=16000)
    # One window per hop start; the trailing partial window is kept so the
    # tail of the file is not dropped (prepare_for_spectra tiles it up).
    expected = len(range(0, len(audio), 16000))
    assert len(windows) == expected
    assert len(windows[0]) == 64600
    assert len(windows[-1]) < 64600  # trailing partial window preserved
    # Consecutive windows must never be identical windows (they advance by hop).
    assert not np.array_equal(windows[0], windows[1])


def test_aggregate_voice_empty_is_insufficient_speech():
    result = aggregate_voice_results([], threshold=THRESHOLD)
    assert result["status"] == "insufficient_speech"
    assert result["is_spoof"] is False
    assert result["windows_analyzed"] == 0
    assert result["raw_bonafide_logit"] == 0.0


def test_aggregate_voice_single_window_decides():
    result = aggregate_voice_results(
        [{"raw_bonafide_logit": -5.0, "is_spoof": True, "threshold": THRESHOLD}],
        threshold=THRESHOLD,
    )
    assert result["status"] == "spoof"
    assert result["is_spoof"] is True
    assert result["raw_bonafide_logit"] == -5.0
    assert result["score"] == 96.0  # <= STRONG_SPOOF_LOGIT


def test_aggregate_voice_majority_and_mean_logit():
    results = [
        {"raw_bonafide_logit": -5.0, "is_spoof": True, "threshold": THRESHOLD},
        {"raw_bonafide_logit": -3.0, "is_spoof": True, "threshold": THRESHOLD},
        {"raw_bonafide_logit": 1.5, "is_spoof": False, "threshold": THRESHOLD},
    ]
    result = aggregate_voice_results(results, threshold=THRESHOLD)
    assert result["is_spoof"] is True  # 2/3 below threshold
    assert result["spoof_windows"] == 2
    assert result["bonafide_windows"] == 1
    assert result["raw_bonafide_logit"] == pytest.approx(round((-5.0 + -3.0 + 1.5) / 3, 4))


def test_aggregate_voice_mixed_is_suspicious():
    results = [
        {"raw_bonafide_logit": -5.0, "is_spoof": True, "threshold": THRESHOLD},
        {"raw_bonafide_logit": 1.5, "is_spoof": False, "threshold": THRESHOLD},
    ]
    result = aggregate_voice_results(results, threshold=THRESHOLD)
    assert result["status"] == "suspicious"  # tie → not a committed verdict
    assert result["is_spoof"] is False


def test_aggregate_voice_all_bonafide():
    results = [
        {"raw_bonafide_logit": 2.0, "is_spoof": False, "threshold": THRESHOLD},
        {"raw_bonafide_logit": 3.0, "is_spoof": False, "threshold": THRESHOLD},
    ]
    result = aggregate_voice_results(results, threshold=THRESHOLD)
    assert result["status"] == "bona_fide"
    assert result["is_spoof"] is False


# ---------------------------------------------------------------------------
# End-to-end pipeline wiring (real decoding, stubbed model/API services)
# ---------------------------------------------------------------------------


def _wav_bytes(sr: int = 48000, seconds: float = 30.0) -> bytes:
    t = np.arange(int(sr * seconds)) / sr
    audio = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class _FakeSpectra:
    loaded = True
    predict_threshold = THRESHOLD

    def predict(self, audio):
        assert audio.shape == (64600,)
        assert audio.dtype == np.float32
        return {"raw_bonafide_logit": -5.0, "is_spoof": True, "threshold": THRESHOLD}


class _FakeTranscriber:
    def __init__(self):
        self.calls = 0

    async def transcribe(self, audio, sample_rate=16000, language=None, ignore_cooldown=False):
        self.calls += 1
        assert sample_rate == 16000
        assert audio.dtype == np.float32
        return {"text": "Please transfer the money now and do not discuss this with anyone"}


class _FakeConversation:
    async def analyze(self, text):
        assert "transfer" in text
        return {
            "urgency": 0.8,
            "financial_request": 0.9,
            "secrecy": 0.7,
            "confidence": 0.9,
            "reasons": ["explicit transfer request", "do not discuss"],
        }


@pytest.mark.asyncio
async def test_pipeline_streams_all_stages_and_real_result(monkeypatch):
    monkeypatch.setattr(famod, "spectra", _FakeSpectra())
    fake_tx = _FakeTranscriber()
    monkeypatch.setattr(famod, "transcription_service", fake_tx)
    monkeypatch.setattr(famod, "conversation_service", _FakeConversation())

    events = []
    async for event in famod.file_analysis_pipeline.stream(
        _wav_bytes(), "scam.wav", language="auto"
    ):
        events.append(event)

    stages = [e["stage"] for e in events if e["type"] == "stage"]
    assert stages == [
        "file_received",
        "audio_decoded",
        "normalized_16khz",
        "spectra_started",
        "spectra_finished",
        "whisper_started",
        "whisper_finished",
        "gpt_started",
        "gpt_finished",
        "risk_calculated",
    ]

    result = events[-1]
    assert result["type"] == "result"
    assert result["file"]["filename"] == "scam.wav"
    assert result["file"]["duration_seconds"] == pytest.approx(30.0, abs=0.5)

    voice = result["voice_analysis"]
    assert voice["status"] == "spoof"
    assert voice["is_spoof"] is True
    assert voice["raw_bonafide_logit"] == -5.0
    assert voice["windows_analyzed"] >= 1
    assert voice["model"] == "Spectra-AASIST3"

    assert "transfer the money" in result["transcript"]["text"]
    assert result["transcript"]["language"] == "auto"

    conv = result["conversation"]
    assert conv["financial_request"] == 0.9
    assert conv["urgency"] == 0.8

    risk = result["risk"]
    assert risk["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    # Real fusion: confirmed spoof + real financial pressure must not floor at 0.
    assert risk["risk_score"] >= 15
    assert risk["reasons"]
    assert risk["recommendation"]

    assert "spectra_finished" in result["timing"]
    assert "risk_calculated" in result["timing"]


@pytest.mark.asyncio
async def test_pipeline_silent_file_yields_no_transcript_no_gpt(monkeypatch):
    monkeypatch.setattr(famod, "spectra", _FakeSpectra())
    monkeypatch.setattr(famod, "transcription_service", _FakeTranscriber())
    gpt_called = {"n": 0}

    class _FakeConversationNoCall:
        async def analyze(self, text):
            gpt_called["n"] += 1
            return {}

    monkeypatch.setattr(famod, "conversation_service", _FakeConversationNoCall())

    # Digital silence suppresses the speech gate for both Spectra and Whisper.
    silence = np.zeros(16000 * 10, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, silence, 16000, format="WAV", subtype="PCM_16")

    stages = []
    result = None
    async for event in famod.file_analysis_pipeline.stream(buf.getvalue(), "silence.wav"):
        if event["type"] == "stage":
            stages.append(event["stage"])
        else:
            result = event

    assert result["voice_analysis"]["status"] == "insufficient_speech"
    assert result["transcript"]["text"] == ""
    assert gpt_called["n"] == 0
    assert "gpt_finished" in stages