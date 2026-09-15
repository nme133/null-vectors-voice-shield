from __future__ import annotations

import numpy as np

from app.core.logging import get_logger

log = get_logger("AUDIO")

PREEMPHASIS_COEFF = 0.97

# Speech-presence gate thresholds.
# Real speech at a typical monitoring mic sits well above these levels
# (RMS >= ~ -50 dBFS); digital silence and low room noise sit far below.
SPEECH_RMS_FLOOR = 3e-3      # overall window RMS cutoff (~ -50 dBFS)
SPEECH_FRAME_RMS = 2e-3      # per-frame RMS cutoff (~ -54 dBFS)
SPEECH_FRAME_MS = 25         # analysis frame length
# A window must contain at least this much *active* signal before it is
# treated as speech.  A 50 ms blip of noise is not speech — requiring ~300 ms
# prevents silence/noise-dominated windows from being analyzed (or fed to
# Whisper) as if they were meaningful speech.
SPEECH_MIN_ACTIVE_SECONDS = 0.3


def to_mono(audio: np.ndarray) -> np.ndarray:
    """Convert multi-channel audio to mono by averaging.

    Handles both (channels, frames) and (frames, channels) layouts by
    averaging over the smaller axis (assumed to be the channel dimension).
    """
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        if audio.shape[0] <= audio.shape[1]:
            return audio.mean(axis=0)
        return audio.mean(axis=1)
    raise ValueError(f"Unexpected audio shape: {audio.shape}")


def resample(audio: np.ndarray, src_rate: int, dst_rate: int = 16000) -> np.ndarray:
    """Resample audio using linear interpolation (deterministic, no libs needed)."""
    if src_rate == dst_rate:
        return audio.astype(np.float32) if audio.dtype != np.float32 else audio
    ratio = dst_rate / src_rate
    n_output = int(np.ceil(len(audio) * ratio))
    output = np.empty(n_output, dtype=np.float32)
    for i in range(n_output):
        pos = i / ratio
        lo = int(pos)
        hi = lo + 1
        frac = pos - lo
        if hi < len(audio):
            output[i] = audio[lo] * (1 - frac) + audio[hi] * frac
        elif lo < len(audio):
            output[i] = audio[lo]
        else:
            output[i] = 0.0
    return output


def normalize_peak(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Peak-normalize audio to ``target_peak``."""
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-8:
        return audio
    return (audio / peak * target_peak).astype(np.float32)


def apply_preemphasis(audio: np.ndarray, coeff: float = PREEMPHASIS_COEFF) -> np.ndarray:
    """Apply pre-emphasis filter: y[n] = x[n] - coeff * x[n-1]."""
    out = np.empty_like(audio, dtype=np.float32)
    out[0] = audio[0]
    for i in range(1, len(audio)):
        out[i] = audio[i] - coeff * audio[i - 1]
    return out


def detect_speech(
    audio: np.ndarray,
    sample_rate: int = 16000,
    frame_ms: int = SPEECH_FRAME_MS,
    min_active_seconds: float = SPEECH_MIN_ACTIVE_SECONDS,
) -> bool:
    """Cheap deterministic speech-presence gate.

    Returns True only when the window contains genuine speech energy, so we
    never feed pure silence / noise bursts to the spoof classifier.  Uses
    per-frame RMS energy: the overall window must clear an absolute RMS floor
    *and* contain at least ``min_active_seconds`` of active signal.  This is
    deliberately conservative on speech (errs toward NOT analyzing silence or
    brief noise blips) while still accepting short utterances.
    """
    if audio.ndim != 1:
        audio = to_mono(audio)
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    frame_len = int(sample_rate * frame_ms / 1000)
    if frame_len < 1:
        frame_len = 1
    n_frames = len(audio) // frame_len
    if n_frames < 1:
        return False

    usable = n_frames * frame_len
    frames = audio[:usable].reshape(n_frames, frame_len)
    frame_energies = np.mean(frames.astype(np.float64) ** 2, axis=1)
    overall_rms = float(np.sqrt(np.mean(frame_energies)))
    active_frames = int(np.sum(np.sqrt(frame_energies) >= SPEECH_FRAME_RMS))
    min_frames = max(1, int(round(min_active_seconds * 1000 / max(frame_ms, 1))))

    return overall_rms >= SPEECH_RMS_FLOOR and active_frames >= min_frames


def prepare_for_spectra(
    audio: np.ndarray,
    sample_rate: int = 16000,
    n_samples: int = 64600,
) -> np.ndarray:
    """Full preprocessing pipeline for Spectra-AASIST3.

    1. to mono
    2. resample to 16 kHz
    3. peak-normalize
    4. pre-emphasis
    5. pad/tile to exactly ``n_samples`` samples

    Returns a float32 numpy array of shape ``(n_samples,)``.
    """
    audio = to_mono(audio)
    if sample_rate != 16000:
        audio = resample(audio, sample_rate, 16000)
    audio = normalize_peak(audio)
    audio = apply_preemphasis(audio)
    # Deterministic first-N-sample window (no random crop)
    if len(audio) >= n_samples:
        return audio[:n_samples].astype(np.float32)
    available = audio.copy()
    repeats = int(n_samples / max(len(available), 1)) + 1
    tiled = np.tile(available, repeats)[:n_samples]
    return tiled.astype(np.float32)
