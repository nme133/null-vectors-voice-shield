from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.audio.buffer import RollingAudioBuffer, TARGET_SAMPLE_RATE
from app.audio.processing import detect_speech, prepare_for_spectra
from app.core.config import settings
from app.core.latency import PipelineTiming
from app.core.logging import get_logger
from app.models.spectra import spectra
from app.schemas.messages import (
    ClientMessage,
    ConnectedMessage,
    ConversationAnalysisUpdate,
    ErrorMessage,
    EventMessage,
    RiskUpdate,
    TranscriptUpdate,
    VoiceAnalysisUpdate,
)
from app.services.conversation import SIGNAL_FIELDS, conversation_service
from app.services.risk_engine import risk_engine, score_to_display
from app.services.transcription import (
    MIN_NEW_AUDIO_SECONDS,
    SUPPORTED_LANGUAGES,
    normalized_language_code,
    texts_are_duplicate,
    transcription_service,
)

log = get_logger("SERVER")
# Dedicated LLM tag so the conversation-analysis pipeline logs as [LLM] (see
# app/services/conversation.py for the [LLM] GPT-OSS request/response logs).
llm_log = get_logger("LLM")

router = APIRouter()

# ---------------------------------------------------------------------------
# Voice decision temporal persistence.
#
# Spectra-AASIST3 outputs a bona-fide logit per ~4 s window.  Raw logits from
# adjacent, overlapping windows flicker around the threshold on real speech.
# We are deliberately CONSERVATIVE about committing to a verdict:
#   * only run inference on windows that contain genuine speech energy
#     (silence is not evidence of a human voice);
#   * advance the spectra window by a fixed hop (default 1 s = one incoming
#     audio chunk) using a sample cursor against the SAME rolling buffer, so
#     each run scores freshly-appended audio and never re-scores the exact
#     same window twice;
#   * EMA-smooth the logit only for the displayed number (an instrument
#     reading, not a probability);
#   * keep a consecutive-window vote counter — NOT a signed streak that must
#     be walked back — so a single noisy window cannot flip the reported
#     spoof/bona-fide verdict;
#   * require THREE consecutive consistent sub-threshold windows before
#     committing to "Possible AI/Spoof" (hysteresis), and THREE consecutive
#     at/above-threshold windows before committing to "Likely Human", so the
#     state cannot rapidly flip AI -> Human -> AI;
#   * surface a three-way status — "spoof", "suspicious", "bona_fide" — where
#     only sustained agreement commits to AI or human; everything in between
#     (including a flipped window) is reported as suspicious/insufficient,
#     never silently declared human.
#
# Engine architecture (real-time decoupling):
#
#     AUDIO
#      ├──→ [receive loop] schedule newest speech window (latest-wins)
#      │         └──→ Spectra worker task → voice evidence → voice_analysis
#      │                    → risk engine → risk_update (immediately)
#      │
#      └──→ [transcription worker] new audio → Whisper → transcript
#                └──→ conversation worker task → GPT-OSS → conversation update
#                          → risk engine → risk_update (immediately)
#
# The receive loop NEVER runs GPU inference directly: it only appends audio
# and schedules work.  Spectra inference runs in a worker task using a thread
# executor (the torch call is blocking), so WebSocket audio ingestion, the
# Whisper worker, the GPT-OSS worker and the risk ticker all stay concurrent.
# Each consumer queue is bounded and latest-wins, so stale windows/transcripts
# are dropped rather than queued into a backlog that finishes old audio after
# new audio has already arrived.
# ---------------------------------------------------------------------------
VOICE_EMA_ALPHA = 0.5         # smoothed display number; recent windows count evenly
VOICE_STREAK_MAX = 5          # cap on the consecutive-vote counter
SPOOF_CONFIRM_STREAK = 3      # consecutive sub-threshold windows -> spoof (conservative)
BONA_CONFIRM_STREAK = 3       # consecutive at/above-threshold windows -> bona-fide (conservative)
INSUFFICIENT_RECHECK_SECONDS = 6.0  # how often to re-notify "listening" state

# Live risk ticker: re-emits a risk_update every second from the current
# rolling-buffer signals so the gauge reflects live data even when no new
# Spectra inference or transcript has completed.
RISK_TICK_INTERVAL = 1.0

# Transcription worker wake-up.
#
# The receive loop signals a per-session asyncio.Event the moment a
# speech-bearing chunk arrives AND MIN_NEW_AUDIO_SECONDS of fresh audio has
# accumulated, so Whisper is requested as soon as a useful chunk exists instead
# of waiting out a fixed poll interval.  This fallback poll is only a safety
# net against a missed signal; it costs ~4 cheap wake-ups/second while idle.
TRANSCRIPTION_POLL_SECONDS = 0.25
# Soft ceiling on a single Whisper round trip.  If a request runs this long it
# is preempted and the newest accumulated audio is used instead, so a slow or
# hung upstream request can never stall transcription of newer audio.
TRANSCRIPTION_SOFT_TIMEOUT = 8.0

# Bounded, latest-wins consumer queues.  At most one item may be pending; a
# newer item replaces an older one, so the consumers always work on the most
# recent evidence and never have to drain a backlog of stale work.
SPECTRA_WINDOW_QUEUE_MAX = 1
CONVERSATION_QUEUE_MAX = 1


@dataclass
class SessionState:
    """Per-session state combining all analysis signals."""
    voice_signal: dict[str, Any] = field(default_factory=lambda: {
        "is_spoof": False,
        "seen": False,
        "streak": 0,
        "smoothed_logit": 0.0,
        "status": "insufficient_speech",
        "score": 0.0,
        "last_insufficient_announced": -1e9,
    })
    conversation_signals: dict = field(default_factory=lambda: {
        "urgency": 0.0, "authority_impersonation": 0.0, "financial_request": 0.0,
        "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0,
        "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0,
        "confidence": 0.0, "reasons": [],
    })
    transcript_log: list[str] = field(default_factory=list)
    # Whisper language (None => automatic detection), set via control message.
    language: str | None = None
    # Cursor tracking how much audio has already been handed to Whisper, so
    # transcripts only ever come from *new* audio (no repeat hallucinations).
    transcription_cursor: int = 0
    # Cursor tracking how much audio has already been scored by Spectra, so
    # consecutive windows advance by at least SPECTRA_HOP_SECONDS of NEW audio
    # and never re-score the exact same samples.
    spectra_cursor: int = 0

    def reset(self) -> None:
        """Reset per-session signals in place.

        The background workers hold a reference to this SAME instance, so they
        must see the reset state too.  Rebinding to a fresh object would split
        the session in two (main loop vs. workers) and is a bug source.
        """
        self.voice_signal = {
            "is_spoof": False,
            "seen": False,
            "streak": 0,
            "smoothed_logit": 0.0,
            "status": "insufficient_speech",
            "score": 0.0,
            "last_insufficient_announced": -1e9,
        }
        self.conversation_signals = {
            "urgency": 0.0, "authority_impersonation": 0.0, "financial_request": 0.0,
            "credential_request": 0.0, "otp_request": 0.0, "threat": 0.0,
            "secrecy": 0.0, "persuasion": 0.0, "repeated_confirmation": 0.0,
            "confidence": 0.0, "reasons": [],
        }
        self.transcript_log = []
        self.transcription_cursor = 0
        self.spectra_cursor = 0


def _replace_latest(queue: asyncio.Queue, item: Any) -> None:
    """Insert ``item`` into a bounded queue, dropping the oldest pending item.

    Keeps at most one item queued; if something is still waiting when a newer
    item arrives, the stale one is discarded.  Consumers therefore always work
    on the most recent data and never process a backlog of obsolete work.
    """
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        pass


def _drain(queue: asyncio.Queue) -> None:
    """Drop any pending items (used when a session is (re)started)."""
    try:
        while True:
            queue.get_nowait()
    except asyncio.QueueEmpty:
        pass


def _merge_conversation_evidence(state: SessionState, analysis: dict) -> None:
    """Merge a GPT-OSS analysis into session-level conversation evidence.

    The analysis is a PARTIAL dict (only fields the model actually returned).
    Merge rules:
      * numeric signals: running MAX over the session — a later, low/empty
        analysis can never zero out strong evidence an earlier line already
        established.  New strong evidence raises the stored value.
      * confidence: running MAX, same rationale.
      * reasons: accumulate unique entries (deduped, capped).
    Doing a wholesale ``state.conversation_signals = analysis`` would let a
    single weak snippet silently erase an established attack pattern — that is
    exactly the failure that pinned the gauge to LOW while the transcript was
    screaming "transfer/confirm/don't discuss".
    """
    cur = state.conversation_signals
    for key in SIGNAL_FIELDS:
        val = analysis.get(key)
        if isinstance(val, bool):
            val = 1.0 if val else 0.0
        if isinstance(val, (int, float)):
            val = max(0.0, min(1.0, float(val)))
            if val > float(cur.get(key, 0.0)):
                cur[key] = val

    conf = analysis.get("confidence")
    if isinstance(conf, bool):
        conf = 1.0 if conf else 0.0
    if isinstance(conf, (int, float)):
        conf = max(0.0, min(1.0, float(conf)))
        if conf > float(cur.get("confidence", 0.0)):
            cur["confidence"] = conf

    seen = set(cur["reasons"])
    for reason in analysis.get("reasons") or []:
        if reason not in seen:
            seen.add(reason)
            cur["reasons"].append(reason)
    cur["reasons"] = cur["reasons"][-15:]


async def _ws_send_json(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        log.debug("Failed to send WS message")


def _make_event(message: str, severity: str = "info", source: str = "engine") -> dict:
    return EventMessage(
        id=f"evt-{uuid.uuid4().hex[:8]}",
        timestamp=time.strftime("%M:%S"),
        message=message,
        severity=severity,
        source=source,
    ).model_dump()


def _vote_streak(current: int, is_below_threshold: bool) -> int:
    """Consecutive-window vote counter around the spoof threshold.

    Positive counts consecutive windows BELOW the bona-fide threshold (spoof
    votes); negative counts consecutive windows at/above it (bona-fide votes).
    A single flip resets the count to 1 in the new direction, so a verdict
    only commits after several windows in a row — but an old verdict never has
    to be "walked back" one window at a time.  That walk-back is what made the
    meter cling to RED for ~18 s after switching from an AI voice to a real
    human voice.
    """
    if is_below_threshold:
        return 1 if current <= 0 else min(current + 1, VOICE_STREAK_MAX)
    return -1 if current >= 0 else max(current - 1, -VOICE_STREAK_MAX)


def _update_voice_signal(state: SessionState, logit: float) -> None:
    """Persist the temporally-consistent voice verdict into session state.

    ``logit`` is the raw bona-fide logit for the current window.  The state
    keeps an EMA-smoothed logit for the displayed number and a
    consecutive-window vote counter for the verdict (see ``_vote_streak``).
    The verdict votes on the RAW per-window logit, so it reflects the actual
    classifier decisions; the EMA stays a smoothed display value.
    """
    vs = state.voice_signal

    if not vs["seen"]:
        smoothed = float(logit)
        vs["seen"] = True
    else:
        smoothed = VOICE_EMA_ALPHA * float(logit) + (1.0 - VOICE_EMA_ALPHA) * vs["smoothed_logit"]

    vs["smoothed_logit"] = smoothed
    vs["streak"] = _vote_streak(vs["streak"], logit < spectra.predict_threshold)

    reported_spoof = vs["is_spoof"]
    if vs["streak"] >= SPOOF_CONFIRM_STREAK:
        reported_spoof = True
    elif vs["streak"] <= -BONA_CONFIRM_STREAK:
        reported_spoof = False
    vs["is_spoof"] = reported_spoof

    # Three-way status from the CURRENT evidence streak: "spoof" /
    # "bona_fide" only after sustained agreement commits; a ±1 streak is
    # "suspicious" (never silently declared human).  This makes transitioning
    # out of a previous AI verdict go RED -> SUSPICIOUS -> GREEN within ~2
    # windows instead of clinging to RED.  Insufficient speech is set by the
    # audio loop, not here.
    if vs["streak"] >= SPOOF_CONFIRM_STREAK:
        vs["status"] = "spoof"
    elif vs["streak"] <= -BONA_CONFIRM_STREAK:
        vs["status"] = "bona_fide"
    else:
        vs["status"] = "suspicious"
    vs["score"] = _score_to_display(smoothed)


async def _compute_and_send_risk(ws: WebSocket, state: SessionState, is_spoof: bool, logit: float,
                                 timing: PipelineTiming | None = None) -> None:
    """Combine current voice + conversation signals, compute risk, send update."""
    snapshot = risk_engine.compute(
        is_spoof=is_spoof,
        bonafide_logit=logit,
        conversation_signals=state.conversation_signals,
    )
    if timing:
        timing.mark("risk_updated", f"score={snapshot.risk_score} {snapshot.risk_level}")
    risk_msg = RiskUpdate(
        risk_score=snapshot.risk_score,
        risk_level=snapshot.risk_level,
        voice_score=round(snapshot.voice_component, 1),
        social_score=round(snapshot.social_component, 1),
        action_score=round(snapshot.action_component, 1),
        reasons=snapshot.reasons,
        recommendation=snapshot.recommendation,
    )
    await _ws_send_json(ws, risk_msg.model_dump())
    if timing:
        timing.mark("websocket_sent", "risk_update")


async def _risk_ticker(ws: WebSocket, state: SessionState, active_flag: dict,
                       timing: PipelineTiming | None = None):
    """Background task: re-emit risk updates every second from live signals.

    This keeps the circular risk gauge moving with the rolling buffer at a
    steady 1 Hz cadence, independent of the Spectra inference cadence or how
    often Whisper produces a transcript.
    """
    while active_flag.get("active", False):
        try:
            await asyncio.sleep(RISK_TICK_INTERVAL)
            if not active_flag.get("active", False):
                break
            await _compute_and_send_risk(
                ws, state,
                is_spoof=state.voice_signal["is_spoof"],
                logit=state.voice_signal["smoothed_logit"],
                timing=timing,
            )
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("Risk ticker error")


async def _spectra_worker(ws: WebSocket, state: SessionState, windows: asyncio.Queue, active_flag: dict,
                          timing: PipelineTiming | None = None):
    """Run Spectra inference OFF the WebSocket receive loop.

    The receive loop only *schedules* the newest speech window onto
    ``windows`` (bounded, latest-wins).  This worker runs the blocking torch
    inference in a thread executor, so audio ingestion and every other async
    task keep running while the GPU is busy.  If the GPU falls behind the
    window cadence, stale pending windows are dropped by ``_replace_latest``
    and the model always scores the newest audio.
    """
    while active_flag.get("active", False):
        try:
            window = await windows.get()
        except asyncio.CancelledError:
            break

        if timing:
            timing.mark("spectra_started", f"window={window.shape[0]}")
        try:
            prepared = await asyncio.to_thread(prepare_for_spectra, window, TARGET_SAMPLE_RATE)
            result = await asyncio.to_thread(spectra.predict, prepared)
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("Spectra inference error")
            await _ws_send_json(ws, ErrorMessage(
                message="Voice analysis inference failed",
                code="INFERENCE_ERROR",
            ).model_dump())
            continue
        if timing:
            timing.mark("spectra_finished")

        if not result:
            continue

        vs = state.voice_signal
        raw_logit = result["raw_bonafide_logit"]
        prev_reported_spoof = vs["is_spoof"]
        _update_voice_signal(state, raw_logit)

        if vs["is_spoof"]:
            confidence = "Spoof Detected"
        elif vs["status"] == "bona_fide":
            confidence = "Bona Fide"
        else:
            confidence = "Spoof Signals Confirming"

        voice_msg = VoiceAnalysisUpdate(
            score=round(vs["score"], 1),
            is_spoof=vs["is_spoof"],
            confidence=confidence,
            status=vs["status"],
            raw_bonafide_logit=round(raw_logit, 4),
        )
        await _ws_send_json(ws, voice_msg.model_dump())
        if timing:
            timing.mark("websocket_sent", "voice_analysis status=" + vs["status"])

        # Voice signal changed → recompute risk immediately.  This does NOT
        # wait for Whisper or GPT-OSS.
        await _compute_and_send_risk(
            ws, state,
            is_spoof=vs["is_spoof"],
            logit=vs["smoothed_logit"],
            timing=timing,
        )

        # Emit a spoof event only on a state transition, never on every
        # overlapping window.
        if vs["is_spoof"] and not prev_reported_spoof:
            await _ws_send_json(ws, _make_event(
                "Acoustic spoof indicators detected in voice",
                severity="warning", source="voice"))


async def _transcription_worker(ws: WebSocket, buffer: RollingAudioBuffer, state: SessionState,
                                analysis_queue: asyncio.Queue, active_flag: dict,
                                new_audio_event: asyncio.Event,
                                timing: PipelineTiming | None = None):
    """Background task: transcribe NEW audio as soon as it is useful.

    Wake model:
      - The receive loop sets ``new_audio_event`` the moment a speech-bearing
        chunk arrives AND at least MIN_NEW_AUDIO_SECONDS of un-transcribed
        audio has accumulated.  The worker therefore wakes the instant a useful
        chunk exists instead of sleeping a fixed poll interval first.
      - A small fallback poll (TRANSCRIPTION_POLL_SECONDS) only guards against
        a missed signal; it never adds seconds of artificial wait.
      - A single worker task means at most ONE Whisper request is in flight; new
        audio arriving mid-request simply re-sets the event, so the *newest*
        accumulated segment is transcribed right after (once the cooldown
        clears) — never a stale backlog.

    Uses a cursor (``transcription_cursor``) so Whisper is only ever fed
    audio that hasn't been transcribed yet — never the same rolling window.
    The cursor is advanced by EXACTLY the snapshot length handed to Whisper
    *before* the API call, so audio that keeps streaming in while the request
    is in flight is covered by the next wake instead of being skipped over or
    transcribed twice.

    The speech gate (``detect_speech``) lives inside the transcription service
    as the final safety net: silence is never sent to Whisper, so no Whisper
    request (and therefore no GPT-OSS request) ever runs on silence.

    The GPT-OSS analysis is handed to a separate ``_conversation_worker`` via
    ``analysis_queue`` — this worker never blocks the next Whisper poll on an
    LLM round trip.
    """
    while active_flag.get("active", False):
        try:
            if not new_audio_event.is_set():
                await asyncio.wait_for(new_audio_event.wait(), timeout=TRANSCRIPTION_POLL_SECONDS)
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            break
        new_audio_event.clear()

        try:
            # Global per-provider cooldown: while cooling down we simply don't
            # consume audio, so nothing is dropped — it just accumulates and is
            # covered by a later wake.
            if not transcription_service.should_transcribe():
                continue

            # Only look at audio received since the last transcription.
            segment = buffer.get_new_since(state.transcription_cursor)
            if segment.size == 0:
                continue
            if len(segment) / TARGET_SAMPLE_RATE < MIN_NEW_AUDIO_SECONDS:
                continue

            log.debug("Transcription worker: analyzing %.1f s of NEW audio",
                      len(segment) / TARGET_SAMPLE_RATE)

            # Consume exactly what Whisper is about to receive.
            state.transcription_cursor += len(segment)

            if timing:
                timing.mark("whisper_started", f"audio={len(segment) / TARGET_SAMPLE_RATE:.2f}s")
            try:
                result = await asyncio.wait_for(
                    transcription_service.transcribe(
                        segment, TARGET_SAMPLE_RATE, language=state.language),
                    timeout=TRANSCRIPTION_SOFT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                if timing:
                    timing.mark("whisper_finished", "preempted")
                log.warning("Transcription preempted after %.0fs "
                            "(newer audio preferred)", TRANSCRIPTION_SOFT_TIMEOUT)
                continue
            if timing:
                timing.mark("whisper_finished")

            if not (result and result["text"].strip()):
                continue
            text = result["text"].strip()

            # Drop near-duplicate hallucinated lines (same rolling audio or
            # Whisper repeating a stale phrase over new silence).
            prev = state.transcript_log[-1] if state.transcript_log else None
            if texts_are_duplicate(text, prev):
                log.debug("Skipped duplicate transcript line: %r", text[:60])
                continue

            state.transcript_log.append(text)
            if len(state.transcript_log) > 5:
                state.transcript_log = state.transcript_log[-5:]

            tx_msg = TranscriptUpdate(
                id=f"tx-{uuid.uuid4().hex[:8]}",
                timestamp=time.strftime("%M:%S"),
                text=text,
            )
            await _ws_send_json(ws, tx_msg.model_dump())
            if timing:
                timing.mark("websocket_sent", "transcript")

            # Schedule conversation analysis (latest-wins) without waiting for
            # it here.
            _replace_latest(analysis_queue, text)
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("Transcription worker error")
            await asyncio.sleep(1.0)


async def _conversation_worker(ws: WebSocket, state: SessionState,
                               analysis_queue: asyncio.Queue, active_flag: dict,
                               timing: PipelineTiming | None = None):
    """Analyze the latest transcript with GPT-OSS independently of Whisper.

    Runs concurrently with the transcription worker, so Whisper never waits on
    an LLM round trip and the LLM never re-analyzes transcripts already
    handed to it (latest-wins queue).  When a conversation analysis completes
    it refreshes the conversation evidence and re-emits risk on that signal
    alone — no voice inference is needed.

    Each analysis sees the NEW transcript PLUS a bounded recent-context window
    (last few lines), so the model can recognize an attack pattern building
    across turns without ever receiving the whole call.
    """
    while active_flag.get("active", False):
        try:
            text = await analysis_queue.get()
        except asyncio.CancelledError:
            break

        # New transcript + small relevant recent context (bounded).  The
        # newest line is already the tail of transcript_log; keep tokens low.
        recent = state.transcript_log[-4:]
        analysis_text = "\n".join(recent) or text

        try:
            if timing:
                timing.mark("gpt_started", f"n_lines={len(recent)}")
            analysis = await conversation_service.analyze(analysis_text)
            if timing:
                timing.mark("gpt_finished")
            _merge_conversation_evidence(state, analysis)
            cur = state.conversation_signals
            conv_msg = ConversationAnalysisUpdate(
                urgency=cur.get("urgency", 0.0),
                authority_impersonation=cur.get("authority_impersonation", 0.0),
                financial_request=cur.get("financial_request", 0.0),
                credential_request=cur.get("credential_request", 0.0),
                otp_request=cur.get("otp_request", 0.0),
                threat=cur.get("threat", 0.0),
                secrecy=cur.get("secrecy", 0.0),
                persuasion=cur.get("persuasion", 0.0),
                repeated_confirmation=cur.get("repeated_confirmation", 0.0),
                confidence=cur.get("confidence", 0.0),
                reasons=cur.get("reasons", []),
            )
            await _ws_send_json(ws, conv_msg.model_dump())
            if timing:
                timing.mark("websocket_sent", "conversation_analysis")
            llm_log.info("[LLM TRACE] CONVERSATION_ANALYSIS SENT urgency=%s financial=%s reasons=%d",
                         cur.get("urgency", 0.0), cur.get("financial_request", 0.0),
                         len(cur.get("reasons", [])))

            vs = state.voice_signal
            await _compute_and_send_risk(
                ws, state,
                is_spoof=vs["is_spoof"],
                logit=vs["smoothed_logit"],
                timing=timing,
            )
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("Conversation worker error")
            await asyncio.sleep(1.0)


def _score_to_display(logit: float) -> float:
    """Map raw bona-fide logit to a 0-100 spoof display index.

    See ``risk_engine.score_to_display`` for the anchor definition; the live
    path uses the model's own loaded threshold.
    """
    return score_to_display(logit, threshold=spectra.predict_threshold)


@router.websocket("/ws/audio")
@router.websocket("/api/v1/stream")
async def audio_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for real-time audio analysis.

    Client → Server:
      - Binary frames: float32 PCM mono 16 kHz audio chunks
      - Text JSON: {"type": ..., "data": {...}} control messages
        (ping / start_session / end_session / set_language
        where set_language.data = {"language": "hi" | "auto" | ...})

    Server → Client (structured JSON):
      - connected, event, voice_analysis, transcript,
        conversation_analysis, risk_update, error
    """
    await websocket.accept()
    log.info("WebSocket client connected")

    session_id = uuid.uuid4().hex[:8]
    timing = PipelineTiming(session_id=session_id)
    timing.mark("session_start")

    buffer = RollingAudioBuffer(sample_rate=TARGET_SAMPLE_RATE, max_seconds=15)
    state = SessionState()

    await _ws_send_json(websocket, ConnectedMessage(
        device=settings.device,
        spectra_loaded=spectra.loaded,
        demo_mode=settings.demo_mode,
    ).model_dump())

    if spectra.loaded:
        await _ws_send_json(websocket, _make_event(
            "Voice analysis pipeline active", severity="info", source="audio"))
    else:
        await _ws_send_json(websocket, _make_event(
            "Voice analysis unavailable (model not loaded)", severity="warning", source="audio"))

    active_flag = {"active": True}
    # Bounded, latest-wins work queues (see _replace_latest).
    windows: asyncio.Queue = asyncio.Queue(maxsize=SPECTRA_WINDOW_QUEUE_MAX)
    analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=CONVERSATION_QUEUE_MAX)
    # Set by the receive loop as soon as useful, speech-bearing audio has
    # accumulated; wakes Whisper immediately (see _transcription_worker).
    new_audio_event: asyncio.Event = asyncio.Event()

    transcription_task = asyncio.create_task(
        _transcription_worker(websocket, buffer, state, analysis_queue, active_flag,
                              new_audio_event, timing)
    )
    spectra_task = asyncio.create_task(
        _spectra_worker(websocket, state, windows, active_flag, timing)
    )
    conversation_task = asyncio.create_task(
        _conversation_worker(websocket, state, analysis_queue, active_flag, timing)
    )
    risk_ticker_task = asyncio.create_task(
        _risk_ticker(websocket, state, active_flag, timing)
    )

    try:
        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if msg.get("bytes") is not None:
                raw = msg["bytes"]
                audio = np.frombuffer(raw, dtype=np.float32)
                if audio.size == 0:
                    continue

                timing.mark("audio_received", f"samples={audio.size}")
                buffer.append(audio)

                vs = state.voice_signal

                # Speech-gated transcription trigger: wake Whisper immediately
                # once a speech-bearing chunk has arrived AND at least
                # MIN_NEW_AUDIO_SECONDS of fresh audio has accumulated.  Silence
                # never trips the event and silence never reaches Whisper (the
                # transcription service re-gates), so no Whisper/GPT-OSS work
                # runs while nobody is talking.
                min_new_samples = int(MIN_NEW_AUDIO_SECONDS * TARGET_SAMPLE_RATE)
                if (
                    buffer.total_received - state.transcription_cursor >= min_new_samples
                    and detect_speech(audio, TARGET_SAMPLE_RATE)
                ):
                    new_audio_event.set()

                if buffer.has_enough and spectra.loaded:
                    # Rolling-hop gate: schedule a window only after at least
                    # one hop of NEW audio has arrived since the last run.  The
                    # window is the newest 64,600 samples of the SAME rolling
                    # buffer, so consecutive windows overlap by (window - hop)
                    # and each run covers freshly-appended audio — never the
                    # identical window twice.  Hop defaults to 1 s (one chunk);
                    # raise SPECTRA_HOP_SECONDS if GPU load demands it.
                    hop = max(1, int(settings.spectra_hop_seconds * TARGET_SAMPLE_RATE))
                    if buffer.total_received - state.spectra_cursor < hop:
                        continue

                    window = buffer.get_window(64600)

                    # Speech/silence gate: never run the spoof classifier on
                    # silence or noise-only windows.  A low-energy window is NOT
                    # evidence of a human voice — surface it as insufficient
                    # speech and do not let it move the risk score.  The cursor
                    # is intentionally NOT advanced here, so the gate stays
                    # armed and the "listening" state is re-notified every
                    # INSUFFICIENT_RECHECK_SECONDS while silence persists.
                    if not detect_speech(window, TARGET_SAMPLE_RATE):
                        now = time.monotonic()
                        if now - vs["last_insufficient_announced"] >= INSUFFICIENT_RECHECK_SECONDS:
                            vs["last_insufficient_announced"] = now
                            vs["status"] = "insufficient_speech"
                            voice_msg = VoiceAnalysisUpdate(
                                score=round(vs["score"], 1),
                                is_spoof=vs["is_spoof"],
                                confidence="Insufficient Speech",
                                status="insufficient_speech",
                                raw_bonafide_logit=round(vs["smoothed_logit"], 4),
                            )
                            await _ws_send_json(websocket, voice_msg.model_dump())
                        continue

                    vs["last_insufficient_announced"] = -1e9
                    state.spectra_cursor = buffer.total_received
                    timing.mark("speech_detected", "spectra window")

                    # Schedule the newest speech window for the Spectra worker.
                    # This is O(sample-copy) work; the blocking GPU call runs
                    # in _spectra_worker, not here, so ingestion never blocks.
                    _replace_latest(windows, window)
                continue

            if msg.get("text"):
                try:
                    data = json.loads(msg["text"])
                    client_msg = ClientMessage(**data)
                except Exception:
                    log.warning("Invalid JSON message: %s", str(msg["text"])[:200])
                    continue

                if client_msg.type == "ping":
                    await _ws_send_json(websocket, {"type": "pong"})
                elif client_msg.type == "start_session":
                    risk_engine.reset()
                    buffer.clear()
                    # Reset in place so the running worker tasks (which hold a
                    # reference to this same SessionState) see the fresh session.
                    state.reset()
                    _drain(windows)
                    _drain(analysis_queue)
                    new_audio_event.clear()
                    await _ws_send_json(websocket, _make_event(
                        "New monitoring session started", severity="info", source="engine"))
                elif client_msg.type == "end_session":
                    active_flag["active"] = False
                    risk_engine.reset()
                    await _ws_send_json(websocket, _make_event(
                        "Monitoring session ended", severity="info", source="engine"))
                elif client_msg.type == "set_language":
                    code = normalized_language_code(
                        str(client_msg.data.get("language")) if client_msg.data else None)
                    state.language = code
                    lang_label = SUPPORTED_LANGUAGES.get(code, "Auto Detect")
                    await _ws_send_json(websocket, _make_event(
                        f"Transcription language set to {lang_label}",
                        severity="info", source="engine"))

    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
    except Exception:
        log.exception("WebSocket error")
    finally:
        active_flag["active"] = False
        transcription_task.cancel()
        spectra_task.cancel()
        conversation_task.cancel()
        risk_ticker_task.cancel()
        for task in (transcription_task, spectra_task, conversation_task, risk_ticker_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        risk_engine.reset()
        buffer.clear()
        log.info("Session cleaned up")