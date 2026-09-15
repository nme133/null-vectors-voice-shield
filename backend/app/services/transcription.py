from __future__ import annotations

import difflib
import io
import time

import httpx
import numpy as np
import soundfile as sf

from app.audio.processing import detect_speech
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("WHISPER")

# Minimum segment length to bother transcribing (seconds).  1.0 s is the
# smallest practical chunk for whisper-large-v3-turbo on live speech: enough
# phonetic/contextual content for reliable output while avoiding the
# multi-second withhold that delays conversation-derived risk.  Anything
# shorter risks hallucination and adds nothing.
MIN_TRANSCRIPTION_SECONDS = 1.0
# Cooldown between transcription requests (seconds).  Small enough that a
# fresh utterance is picked up a fraction of a second after the previous
# Whisper round trip, large enough to avoid hammering Groq with near-empty
# segments.
TRANSCRIPTION_COOLDOWN = 0.5
# Minimum amount of *new* audio since the previous transcription.  Combined
# with a cursor (see _transcription_worker) this stops Whisper from being fed
# the same rolling window over and over and hallucinating duplicate text.
# Kept equal to MIN_TRANSCRIPTION_SECONDS so transcripts flow as soon as a
# meaningful utterance has accumulated, rather than withholding several
# seconds of audio that delays conversation-derived risk.
MIN_NEW_AUDIO_SECONDS = 1.0
# Groq Whisper large-v3-turbo model id
WHISPER_MODEL = "whisper-large-v3-turbo"
# Deterministic decoding: temperature 0 gives stable, reproducible output and
# minimizes hallucinated filler on low-confidence audio.
WHISPER_TEMPERATURE = 0

# Supported transcription languages: ISO-639-1 codes understood by Whisper.
# "auto" (None) lets Whisper detect the language itself — we never force "en".
SUPPORTED_LANGUAGES: dict[str, str] = {
    "auto": None,
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
}


def normalized_language_code(code: str | None) -> str | None:
    """Map a UI language code to a Whisper ISO-639-1 code (None => auto detect)."""
    if not code:
        return None
    key = str(code).strip().lower()
    if key in ("auto", "detect", ""):
        return None
    if key in SUPPORTED_LANGUAGES:
        return key
    # Accept a two-letter ISO code directly too
    if len(key) == 2:
        return key
    return None


def texts_are_duplicate(new: str, previous: str | None) -> bool:
    """Conservative duplicate check used to avoid repeated hallucinated lines."""
    if not previous or not new:
        return False
    a, b = new.strip().lower(), previous.strip().lower()
    if a == b:
        return True
    if a in b or b in a:
        return True
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio > 0.9


class TranscriptionService:
    """Wraps Groq Whisper API for speech-to-text transcription."""

    def __init__(self):
        self.last_transcription_time: float = 0.0

    def should_transcribe(self) -> bool:
        return (time.monotonic() - self.last_transcription_time) >= TRANSCRIPTION_COOLDOWN

    async def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
        ignore_cooldown: bool = False,
    ) -> dict | None:
        """Transcribe audio via Groq Whisper API.

        - ``language`` is a Whisper ISO-639-1 code, or ``None`` for automatic
          detection.  Automatic detection is the default — Whisper is never
          forced to "en" when the caller is speaking another language.
        - Speech gating happens here as a final safety net: silence / very
          weak audio is never sent to Whisper (see ``detect_speech``).
        - ``ignore_cooldown`` bypasses the per-provider rate limiter.  Used by
          the offline file-upload pipeline where each segment of one file is
          transcribed back-to-back; the WebSocket live path never passes it.

        Returns {"text": str} or None when there is nothing meaningful to
        transcribe or on failure.
        """
        if settings.demo_mode:
            return None

        api_key = settings.groq_api_key
        if not api_key:
            log.debug("No GROQ_API_KEY configured, skipping transcription")
            return None

        if len(audio) / sample_rate < MIN_TRANSCRIPTION_SECONDS:
            return None

        # Conservative rule: if the window does not contain enough speech
        # energy, emit no transcript rather than inventing one.
        if not detect_speech(audio, sample_rate):
            log.debug("Transcription skipped: no sufficient speech energy in window")
            return None

        if not self.should_transcribe() and not ignore_cooldown:
            return None

        lang_code = normalized_language_code(language)

        try:
            wav_bytes = self._audio_to_wav(audio, sample_rate)
        except Exception:
            log.exception("Failed to encode audio to WAV")
            return None

        try:
            post_data: dict = {
                "model": WHISPER_MODEL,
                "temperature": WHISPER_TEMPERATURE,
            }
            if lang_code is not None:
                post_data["language"] = lang_code
                log.debug("Whisper language forced to %r", lang_code)
            else:
                log.debug("Whisper language: auto-detect (not forced)")

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    settings.groq_api_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    data=post_data,
                )
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("text", "").strip()
                    self.last_transcription_time = time.monotonic()
                    log.info("Transcription (%s): %s",
                             lang_code or "auto", text[:120])
                    return {"text": text}
                else:
                    log.warning("Whisper API error %d: %s", response.status_code, response.text[:200])
                    return None
        except httpx.TimeoutException:
            log.warning("Whisper API timeout")
            return None
        except Exception:
            log.exception("Whisper API request failed")
            return None

    @staticmethod
    def _audio_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read()


transcription_service = TranscriptionService()