from __future__ import annotations

import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio.processing import to_mono
from app.core.logging import get_logger

log = get_logger("AUDIO")

# File types accepted for the upload analysis endpoint.
ACCEPTED_EXTENSIONS: set[str] = {
    ".wav", ".wave",
    ".mp3",
    ".m4a", ".aac",
    ".ogg", ".oga",
    ".webm",
    ".flac",
    ".opus",
}

# Maximum upload payload accepted by the endpoint (raw compressed bytes).
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

_FFMPEG_EXE: str | None = None


def ffmpeg_binary() -> str:
    """Path to a usable ffmpeg binary (bundled via imageio-ffmpeg), or ""."""
    global _FFMPEG_EXE
    if _FFMPEG_EXE is None:
        try:
            import imageio_ffmpeg

            _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            _FFMPEG_EXE = ""
    return _FFMPEG_EXE


def decode_audio(data: bytes, filename: str = "") -> tuple[np.ndarray, int]:
    """Decode raw audio bytes to a (float32 mono samples, native sample_rate) pair.

    Primary path: libsndfile (soundfile), which natively handles WAV / FLAC /
    OGG / MP3.  Fallback: a bundled ffmpeg 7.x binary (imageio-ffmpeg) used for
    containers libsndfile can't read (M4A/AAC, WEBM/Opus), decoded to a mono
    WAV at the file's native sample rate so the caller still normalizes through
    the project's own resample pipeline.

    Returns:
        (samples, sample_rate) where samples is float32 mono, at the native
        sample rate of the file (NOT yet resampled to 16 kHz).
    """
    if not data:
        raise ValueError("Empty audio file")

    try:
        samples, sr = _decode_soundfile(data)
        log.info("Decoded via libsndfile: %d samples @ %d Hz", len(samples), sr)
        return samples, sr
    except Exception as exc:
        log.debug("libsndfile decode failed for %r: %s", filename, exc)

    samples, sr = _decode_ffmpeg(data, filename)
    log.info("Decoded via ffmpeg fallback: %d samples @ %d Hz", len(samples), sr)
    return samples, sr


def _decode_soundfile(data: bytes) -> tuple[np.ndarray, int]:
    samples, sr = sf.read(BytesIO(data), dtype="float32", always_2d=False)
    if samples.size == 0:
        raise ValueError("Audio file contains no samples")
    samples = to_mono(samples)
    return samples.astype(np.float32), int(sr)


def _decode_ffmpeg(data: bytes, filename: str) -> tuple[np.ndarray, int]:
    exe = ffmpeg_binary()
    if not exe:
        raise ValueError("No ffmpeg decoder available for this file type")

    # Write to a temp file with the original extension so ffmpeg picks the
    # right demuxer (needed for non-seekable-in-pipe containers like MP4).
    suffix = Path(filename).suffix.lower() if filename and Path(filename).suffix else ".bin"
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, f"input{suffix}")
        with open(src_path, "wb") as fh:
            fh.write(data)

        args = [
            exe, "-hide_banner", "-loglevel", "error", "-y",
            "-i", src_path,
            "-vn", "-ac", "1", "-f", "wav", "pipe:1",
        ]
        proc = subprocess.run(args, capture_output=True)
        if proc.returncode != 0 or not proc.stdout:
            err = proc.stderr.decode(errors="replace")[:300] or "decoder returned no audio"
            raise ValueError(f"ffmpeg could not decode audio: {err}")

        samples, sr = sf.read(BytesIO(proc.stdout), dtype="float32", always_2d=False)
        if samples.size == 0:
            raise ValueError("Audio file contains no samples")
        samples = to_mono(samples)
        return samples.astype(np.float32), int(sr)