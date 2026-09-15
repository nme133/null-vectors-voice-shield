import asyncio

import numpy as np

from app.services import transcription as tmod
from app.services.transcription import (
    MIN_TRANSCRIPTION_SECONDS,
    SUPPORTED_LANGUAGES,
    TranscriptionService,
    normalized_language_code,
    texts_are_duplicate,
)


def _speech_window(seconds: float = 4.0) -> np.ndarray:
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_whisper_request_gets_language_parameter(monkeypatch):
    """The selected language must actually reach the Whisper API request.

    'hi' -> post_data["language"] == "hi"; 'auto' -> the language parameter is
    omitted entirely so Whisper auto-detects (never a fake default).
    """
    captured = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"text": "namaste"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers, files, data):
            captured["data"] = dict(data)
            return _FakeResponse()

    monkeypatch.setattr(tmod.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(tmod.settings, "groq_api_key", "test-key")

    async def run(code, **kwargs):
        service = TranscriptionService()
        audio = _speech_window()
        result = await service.transcribe(audio, 16000, language=code, **kwargs)
        return result

    res = asyncio.run(run("hi"))
    assert res == {"text": "namaste"}
    assert captured["data"]["language"] == "hi"

    res = asyncio.run(run("auto"))
    assert res == {"text": "namaste"}
    assert "language" not in captured["data"]

    res = asyncio.run(run(None))
    assert "language" not in captured["data"]


def test_normalized_language_code_auto_returns_none():
    assert normalized_language_code("auto") is None
    assert normalized_language_code(None) is None
    assert normalized_language_code("") is None
    assert normalized_language_code("detect") is None


def test_normalized_language_code_supported():
    assert normalized_language_code("hi") == "hi"
    assert normalized_language_code("TA") == "ta"
    assert normalized_language_code("English") is None  # full name not accepted


def test_normalized_language_code_unknown_returns_none():
    assert normalized_language_code("xyz") is None
    # Any 2-letter ISO code is accepted verbatim (e.g. from Whisper)
    assert normalized_language_code("zz") == "zz"


def test_texts_are_duplicate_identical():
    assert texts_are_duplicate("hello world", "hello world") is True


def test_texts_are_duplicate_substring():
    assert texts_are_duplicate("", "hello") is False
    assert texts_are_duplicate("thank you", "thank you thank you") is True


def test_texts_are_duplicate_high_similarity():
    assert texts_are_duplicate("Hello, how are you today?", "Hello how are you today") is True


def test_texts_are_duplicate_distinct():
    assert texts_are_duplicate("Please transfer the funds now", "The weather is nice today") is False


def test_transcription_service_gate_rejects_short_audio():
    short = np.zeros(int(0.5 * 16000), dtype=np.float32)
    assert len(short) / 16000 < MIN_TRANSCRIPTION_SECONDS


def test_transcription_service_rejects_silence_without_api_call(monkeypatch):
    """Silence must NEVER reach Whisper: no transcription request, therefore
    no conversation/GPT analysis downstream.  The gate returns None before any
    HTTP round trip."""
    called = {"posted": False}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"text": "should never happen"}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            called["posted"] = True
            return _FakeResponse()

    monkeypatch.setattr(tmod.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(tmod.settings, "groq_api_key", "test-key")

    service = TranscriptionService()
    silence = np.zeros(int(2.0 * 16000), dtype=np.float32)
    result = asyncio.run(service.transcribe(silence, 16000))
    assert result is None
    assert called["posted"] is False


def test_supported_languages_include_auto_and_whisper_codes():
    assert "auto" in SUPPORTED_LANGUAGES
    for code in ("en", "hi", "bn", "ta", "te", "mr", "gu", "pa", "ur"):
        assert code in SUPPORTED_LANGUAGES