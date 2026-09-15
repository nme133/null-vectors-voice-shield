import asyncio

import numpy as np
import pytest

from app.api import websocket as wsmod
from app.audio.buffer import RollingAudioBuffer, TARGET_SAMPLE_RATE


class _FakeScamTranscriptService:
    """Fake Whisper: returns the bank-scam transcript instead of calling Groq STT."""

    def __init__(self):
        self.calls = 0
        self.last_transcription_time = 0.0

    def should_transcribe(self) -> bool:
        return True

    async def transcribe(self, audio, sample_rate=16000, language=None):
        self.calls += 1
        await asyncio.sleep(0.01)
        return {
            "text": "I am calling from your bank. Your account has a serious problem. "
            "You need to transfer the money immediately. Send me the OTP so I can "
            "complete the transaction. Do not call the bank."
        }


class _DummyWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, payload: str) -> None:
        import json

        self.sent.append(json.loads(payload))


def _speech(seconds: float) -> np.ndarray:
    sr = TARGET_SAMPLE_RATE
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


@pytest.mark.asyncio
async def test_transcript_triggers_real_gpt_oss_and_sends_conversation_analysis(monkeypatch):
    """The full backend path: Whisper transcript -> Groq GPT-OSS -> conversation_analysis.

    Uses a FAKE Whisper returning the scam transcript but the REAL conversation
    service (real Groq / gpt-oss-120b). The analysis must produce strong
    financial/credential/urgency signals and a conversation_analysis message.
    """
    fake = _FakeScamTranscriptService()
    monkeypatch.setattr(wsmod, "transcription_service", fake)

    ws = _DummyWS()
    buffer = RollingAudioBuffer(sample_rate=TARGET_SAMPLE_RATE, max_seconds=15)
    state = wsmod.SessionState()
    analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    active_flag = {"active": True}
    new_audio_event = asyncio.Event()

    tx_task = asyncio.create_task(
        wsmod._transcription_worker(ws, buffer, state, analysis_queue,
                                    active_flag, new_audio_event)
    )
    conv_task = asyncio.create_task(
        wsmod._conversation_worker(ws, state, analysis_queue, active_flag)
    )

    try:
        buffer.append(_speech(1.4))
        new_audio_event.set()
        for _ in range(60):
            await asyncio.sleep(0.5)
            if any(m.get("type") == "conversation_analysis" for m in ws.sent):
                break
    finally:
        active_flag["active"] = False
        tx_task.cancel()
        conv_task.cancel()
        for task in (tx_task, conv_task):
            try:
                await task
            except asyncio.CancelledError:
                pass

    messages = {m.get("type") for m in ws.sent}
    assert "transcript" in messages, f"got {messages}"
    assert "conversation_analysis" in messages, f"got {messages}"

    conv = next(m for m in ws.sent if m.get("type") == "conversation_analysis")
    assert conv["financial_request"] > 0.5, conv
    assert conv["credential_request"] > 0.5, conv
    assert conv["otp_request"] > 0.5, conv
    assert conv["urgency"] > 0.5, conv
    assert conv["authority_impersonation"] > 0.5, conv
    assert len(conv["reasons"]) >= 1, conv