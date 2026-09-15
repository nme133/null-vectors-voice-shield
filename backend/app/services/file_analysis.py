from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

import numpy as np

from app.audio.decoder import decode_audio
from app.audio.processing import detect_speech, prepare_for_spectra, resample, to_mono
from app.core.config import settings
from app.core.logging import get_logger
from app.models.spectra import WINDOW_SAMPLES, spectra
from app.services.conversation import SIGNAL_FIELDS, conversation_service
from app.services.risk_engine import risk_engine, score_to_display
from app.services.transcription import (
    MIN_TRANSCRIPTION_SECONDS,
    normalized_language_code,
    texts_are_duplicate,
    transcription_service,
)

log = get_logger("FILE-ANALYSIS")

TARGET_SAMPLE_RATE = 16000
# Spectra-AASIST3 requires exactly 64,600 samples (~4.04 s) per inference window.
SPECTRA_WINDOW = WINDOW_SAMPLES
# Groq Whisper uploads are capped at 25 MB of encoded audio.  At 16 kHz PCM_16
# that is ~13 minutes, so long files are segmented into 5-minute chunks, each of
# which stays well under the limit.
TRANSCRIBE_CHUNK_SECONDS = 300.0
# Only the first N minutes of a pathological recording are transcribed, so a
# 3-hour file cannot spin Groq requests indefinitely.
MAX_TRANSCRIBE_SECONDS = 1800.0
# Token-budget guard for the GPT-OSS conversation analysis input.
MAX_CONVERSATION_CHARS = 32000


def plan_spectra_windows(
    audio: np.ndarray,
    window_samples: int = SPECTRA_WINDOW,
    hop_samples: int | None = None,
) -> list[np.ndarray]:
    """Slice 16 kHz mono audio into the overlapping windows Spectra scores.

    - Files SHORTER than the model window: a single window handed to the
      existing padding/tiling behavior inside ``prepare_for_spectra``.
    - Files LONGER than the window: hop through the file with the configured
      Spectra hop (default 1 s = one live chunk), including the final partial
      window so trailing speech is not dropped.  Consecutive windows advance by
      ``hop_samples`` of NEW audio, so no identical window is ever scored twice.
    """
    if hop_samples is None:
        hop_samples = max(1, int(settings.spectra_hop_seconds * TARGET_SAMPLE_RATE))
    audio = np.asarray(audio, dtype=np.float32)
    if len(audio) < window_samples:
        return [audio]
    starts = list(range(0, len(audio), hop_samples))
    return [audio[i:i + window_samples] for i in starts]


def aggregate_voice_results(
    results: list[dict],
    threshold: float | None = None,
) -> dict:
    """Aggregate per-window Spectra raw bonafide logits into a single verdict.

    Each result is the raw ``spectra.predict`` output:
      ``{"raw_bonafide_logit": float, "is_spoof": bool, "threshold": float}``

    Aggregation is deterministic and explained by the reported counts:
      - reported ``raw_bonafide_logit`` = mean over all scored windows;
      - ``is_spoof`` = STRICT MAJORITY of windows below the bona-fide
        threshold (higher logit = more bona-fide-like);
      - a majority-suspect but-mixed file is reported as ``suspicious`` rather
        than a clean verdict;
      - no scored windows (no speech energy anywhere) → ``insufficient_speech``.

    The returned display ``score`` is a 0-100 instrument readout, NOT a
    probability (same mapping as the live WebSocket path).
    """
    if threshold is None:
        threshold = spectra.predict_threshold

    if not results:
        return {
            "score": 0.0,
            "is_spoof": False,
            "confidence": "Insufficient Speech",
            "status": "insufficient_speech",
            "raw_bonafide_logit": 0.0,
            "windows_analyzed": 0,
            "spoof_windows": 0,
            "bonafide_windows": 0,
        }

    logits = [float(r["raw_bonafide_logit"]) for r in results]
    mean_logit = float(np.mean(logits))
    spoof_votes = sum(1 for l in logits if l < threshold)
    total = len(logits)

    if spoof_votes > total // 2:
        status, is_spoof, confidence = "spoof", True, "Spoof Detected"
    elif spoof_votes == 0:
        status, is_spoof, confidence = "bona_fide", False, "Bona Fide"
    else:
        status, is_spoof, confidence = "suspicious", False, "Spoof Signals Confirming"

    return {
        "score": round(score_map(mean_logit, threshold), 1),
        "is_spoof": is_spoof,
        "confidence": confidence,
        "status": status,
        "raw_bonafide_logit": round(mean_logit, 4),
        "windows_analyzed": total,
        "spoof_windows": spoof_votes,
        "bonafide_windows": total - spoof_votes,
    }


def score_map(logit: float, threshold: float) -> float:
    """0-100 spoof signal-strength readout (NOT a probability)."""
    return score_to_display(logit, threshold=threshold)


class FileAnalysisPipeline:
    """Offline audio-file pipeline — real models, real services, no mocks.

    Reuses the EXACT backend singletons the live WebSocket path uses:
    ``spectra`` (Spectra-AASIST3), ``transcription_service`` (Groq Whisper),
    ``conversation_service`` (Groq GPT-OSS) and ``risk_engine``.  Stages are
    streamed as NDJSON events so the UI renders real progress without storing
    the whole response until the final result.
    """

    async def stream(
        self,
        data: bytes,
        filename: str = "",
        language: str = "auto",
    ) -> AsyncIterator[dict[str, Any]]:
        t0 = time.monotonic()
        timing: dict[str, float] = {}

        def emit(stage: str, detail: str = "") -> dict[str, Any]:
            elapsed = round(time.monotonic() - t0, 3)
            timing[stage] = elapsed
            log.info("UPLOAD stage=%s elapsed=%.3fs %s", stage, elapsed, detail)
            return {"type": "stage", "stage": stage, "message": detail, "elapsed": elapsed}

        yield emit("file_received", f"bytes={len(data)} filename={filename}")

        # --- Decode to mono Float32 at the file's native sample rate ---
        samples, src_sr = decode_audio(data, filename)
        yield emit(
            "audio_decoded",
            f"samples={len(samples)} sr={src_sr} duration={len(samples) / src_sr:.2f}s",
        )

        # --- Normalize to Spectra's input format: 16 kHz mono Float32 ---
        audio16 = self._normalize(samples, src_sr)
        yield emit("normalized_16khz", f"samples={len(audio16)} channels=1 sr={TARGET_SAMPLE_RATE}")

        # --- Spectra-AASIST3 (real model, windowed over the file) ---
        windows = plan_spectra_windows(audio16)
        yield emit("spectra_started", f"windows={len(windows)} window={SPECTRA_WINDOW}")
        voice_results: list[dict] = []
        for i, w in enumerate(windows):
            # Same speech gate as the live pipeline: silence is not evidence.
            if not detect_speech(w, TARGET_SAMPLE_RATE):
                log.info("UPLOAD spectra window %d: no speech energy, skipped", i)
                continue
            prepared = prepare_for_spectra(w, TARGET_SAMPLE_RATE)
            result = await asyncio.to_thread(spectra.predict, prepared)
            if isinstance(result, dict) and result.get("raw_bonafide_logit") is not None:
                voice_results.append(result)
        voice = aggregate_voice_results(voice_results)
        yield emit(
            "spectra_finished",
            f"scored={voice['windows_analyzed']}/{len(windows)} "
            f"spoof={voice['spoof_windows']} logit={voice['raw_bonafide_logit']}",
        )

        # --- Whisper (existing Groq service, whole normalized file) ---
        lang_code = normalized_language_code(language)
        yield emit("whisper_started", f"language={lang_code or 'auto'}")
        transcript_text = await self._transcribe_file(audio16, lang_code)
        yield emit("whisper_finished", f"chars={len(transcript_text)}")

        # --- GPT-OSS (existing conversation analysis on the REAL transcript) ---
        signals: dict[str, Any] = {}
        if transcript_text.strip():
            yield emit("gpt_started", f"chars={len(transcript_text[:MAX_CONVERSATION_CHARS])}")
            signals = await conversation_service.analyze(transcript_text[:MAX_CONVERSATION_CHARS])
            yield emit(
                "gpt_finished",
                f"signals={len(signals)} reasons={len(signals.get('reasons') or [])}",
            )
        else:
            yield emit("gpt_started", "no transcript")
            yield emit("gpt_finished", "skipped (no transcript was produced)")

        # --- Risk engine (existing deterministic fusion) ---
        try:
            risk_engine.reset()
            snapshot = risk_engine.compute(
                is_spoof=voice["is_spoof"],
                bonafide_logit=voice["raw_bonafide_logit"],
                conversation_signals={k: signals.get(k, 0.0) for k in SIGNAL_FIELDS},
            )
        finally:
            risk_engine.reset()
        yield emit(
            "risk_calculated",
            f"score={snapshot.risk_score} {snapshot.risk_level} "
            f"voice={snapshot.voice_component:.1f} social={snapshot.social_component:.1f} "
            f"action={snapshot.action_component:.1f}",
        )

        yield {"type": "result",
               "file": {
                   "filename": filename,
                   "size_bytes": len(data),
                   "sample_rate": src_sr,
                   "channels": 1,
                   "duration_seconds": round(len(audio16) / TARGET_SAMPLE_RATE, 2),
               },
               "voice_analysis": {**voice, "model": "Spectra-AASIST3"},
               "transcript": {
                   "text": transcript_text,
                   "language": lang_code or "auto",
                   "chars": len(transcript_text),
               },
               "conversation": {**DEFAULT_CONVERSATION_SIGNALS, **signals},
               "risk": {
                   "risk_score": snapshot.risk_score,
                   "risk_level": snapshot.risk_level,
                   "voice_score": round(snapshot.voice_component, 1),
                   "social_score": round(snapshot.social_component, 1),
                   "action_score": round(snapshot.action_component, 1),
                   "reasons": snapshot.reasons,
                   "recommendation": snapshot.recommendation,
               },
               "timing": timing}

    @staticmethod
    def _normalize(samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """16 kHz mono Float32, using the project's existing audio utilities."""
        mono = to_mono(samples)
        if sample_rate != TARGET_SAMPLE_RATE:
            mono = resample(mono, sample_rate, TARGET_SAMPLE_RATE)
        return np.asarray(mono, dtype=np.float32)

    async def _transcribe_file(self, audio16: np.ndarray, lang_code: str | None) -> str:
        """Send the uploaded audio to the existing Groq Whisper service.

        The whole normalized file is used; very long recordings are segmented
        into ``TRANSCRIBE_CHUNK_SECONDS`` chunks (each comfortably under Groq's
        25 MB cap) and the segment transcripts are joined.  The selected
        language setting is honored: ``None`` (Auto) omits the parameter so
        Whisper auto-detects; otherwise the ISO-639-1 code is passed verbatim.
        Nothing is ever translated into English.
        """
        if len(audio16) / TARGET_SAMPLE_RATE < MIN_TRANSCRIPTION_SECONDS:
            return ""

        max_samples = int(MAX_TRANSCRIBE_SECONDS * TARGET_SAMPLE_RATE)
        transcribe_audio = audio16[:max_samples]
        if len(transcribe_audio) < len(audio16):
            log.warning(
                "UPLOAD transcribing first %.0f s of %.0f s audio",
                MAX_TRANSCRIBE_SECONDS, len(audio16) / TARGET_SAMPLE_RATE,
            )

        chunk_samples = int(TRANSCRIBE_CHUNK_SECONDS * TARGET_SAMPLE_RATE)
        parts: list[str] = []
        for start in range(0, len(transcribe_audio), chunk_samples):
            seg = transcribe_audio[start:start + chunk_samples]
            if not detect_speech(seg, TARGET_SAMPLE_RATE):
                continue
            result = await transcription_service.transcribe(
                seg, TARGET_SAMPLE_RATE, language=lang_code, ignore_cooldown=True,
            )
            if not result or not result.get("text", "").strip():
                continue
            text = result["text"].strip()
            if parts and texts_are_duplicate(text, parts[-1]):
                continue
            parts.append(text)
        return "\n".join(parts)


DEFAULT_CONVERSATION_SIGNALS: dict[str, Any] = {
    "urgency": 0.0,
    "authority_impersonation": 0.0,
    "financial_request": 0.0,
    "credential_request": 0.0,
    "otp_request": 0.0,
    "threat": 0.0,
    "secrecy": 0.0,
    "persuasion": 0.0,
    "repeated_confirmation": 0.0,
    "confidence": 0.0,
    "reasons": [],
}


file_analysis_pipeline = FileAnalysisPipeline()