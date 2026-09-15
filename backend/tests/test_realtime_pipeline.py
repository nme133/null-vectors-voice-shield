import asyncio

import numpy as np
import pytest

from app.api import websocket as wsmod
from app.audio.buffer import RollingAudioBuffer, TARGET_SAMPLE_RATE
from app.core.latency import PipelineTiming


class _FakeTranscriptService:
    """Stands in for the real Groq transcription service in worker tests."""

    def __init__(self):
        self.calls: list[tuple[int, int]] = []
        self.last_transcription_time = 0.0

    def should_transcribe(self) -> bool:
        return True

    async def transcribe(self, audio, sample_rate=16000, language=None):
        self.calls.append((len(audio), sample_rate))
        await asyncio.sleep(0.01)
        return {"text": "hello world"}


class _DummyWS:
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, payload: str) -> None:
        self.sent.append(payload)


def _speech_seconds(seconds: float) -> np.ndarray:
    sr = TARGET_SAMPLE_RATE
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


@pytest.mark.asyncio
async def test_transcription_worker_wakes_immediately_on_event(monkeypatch):
    """A speech-bearing segment must be handed to Whisper as soon as the
    receive loop has accumulated enough new audio — no fixed 1 s sleep first."""
    fake = _FakeTranscriptService()
    monkeypatch.setattr(wsmod, "transcription_service", fake)

    ws = _DummyWS()
    buffer = RollingAudioBuffer(sample_rate=TARGET_SAMPLE_RATE, max_seconds=15)
    state = wsmod.SessionState()
    analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    active_flag = {"active": True}
    new_audio_event = asyncio.Event()

    task = asyncio.create_task(
        wsmod._transcription_worker(ws, buffer, state, analysis_queue,
                                    active_flag, new_audio_event)
    )

    # 1.2 s of real speech energy appended, then the receive-loop signal.
    buffer.append(_speech_seconds(1.2))
    new_audio_event.set()

    await asyncio.sleep(0.2)
    active_flag["active"] = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert fake.calls, "whisper must be requested for a useful speech chunk"
    duration = fake.calls[0][0] / TARGET_SAMPLE_RATE
    assert duration >= wsmod.MIN_NEW_AUDIO_SECONDS
    assert len(state.transcript_log) == 1
    assert state.transcript_log[0] == "hello world"
    assert not analysis_queue.empty()


@pytest.mark.asyncio
async def test_transcription_worker_ignores_stale_event_without_audio(monkeypatch):
    """Waking up must never send an empty segment to Whisper."""
    fake = _FakeTranscriptService()
    monkeypatch.setattr(wsmod, "transcription_service", fake)

    ws = _DummyWS()
    buffer = RollingAudioBuffer(sample_rate=TARGET_SAMPLE_RATE, max_seconds=15)
    state = wsmod.SessionState()
    analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    active_flag = {"active": True}
    new_audio_event = asyncio.Event()
    new_audio_event.set()  # stale signal, no audio appended

    task = asyncio.create_task(
        wsmod._transcription_worker(ws, buffer, state, analysis_queue,
                                    active_flag, new_audio_event)
    )

    await asyncio.sleep(0.1)
    active_flag["active"] = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert fake.calls == []


def test_pipeline_timing_records_monotonic_stages():
    t = PipelineTiming("latency-test")
    t.mark("session_start")
    t.mark("audio_received")
    t.mark("speech_detected")
    t.mark("whisper_started")
    t.mark("whisper_finished")
    assert set(t._marks) == {
        "session_start", "audio_received", "speech_detected",
        "whisper_started", "whisper_finished",
    }
    # Monotonic ordering preserved.
    marks = t._marks
    assert marks["speech_detected"] >= marks["audio_received"]
    assert marks["whisper_finished"] > marks["whisper_started"]