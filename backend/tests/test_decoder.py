import io

import numpy as np
import soundfile as sf

from app.audio.decoder import decode_audio, ffmpeg_binary


def _sine_wav_bytes(sr: int = 48000, seconds: float = 1.0, stereo: bool = True) -> bytes:
    t = np.arange(int(sr * seconds)) / sr
    left = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    right = (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    audio = np.stack([left, right], axis=1) if stereo else left
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_decode_wav_stereo_48k_becomes_mono_float32():
    samples, sr = decode_audio(_sine_wav_bytes(), "test.wav")
    assert sr == 48000
    assert samples.ndim == 1
    assert samples.dtype == np.float32
    assert len(samples) == 48000


def test_decode_mono_wav_keeps_real_sample_rate():
    samples, sr = decode_audio(_sine_wav_bytes(sr=44100, stereo=False), "test.wav")
    assert sr == 44100
    assert samples.ndim == 1


def test_decode_garbage_raises():
    try:
        decode_audio(b"this is definitely not audio data at all", "garbage.bin")
        raised = False
    except ValueError:
        raised = True
    assert raised


def _transcode(source: bytes, src_name: str, dst_name: str) -> bytes:
    import os
    import subprocess
    import tempfile

    exe = ffmpeg_binary()
    assert exe, "ffmpeg binary unavailable"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, src_name)
        dst = os.path.join(tmp, dst_name)
        with open(src, "wb") as fh:
            fh.write(source)
        result = subprocess.run(
            [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-c:a", "aac", dst],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace")[:300])
        with open(dst, "rb") as fh:
            return fh.read()


def test_decode_m4a_uses_ffmpeg_fallback():
    m4a = _transcode(_sine_wav_bytes(), "src.wav", "out.m4a")
    samples, sr = decode_audio(m4a, "out.m4a")
    assert samples.ndim == 1
    assert samples.dtype == np.float32
    # Native rate preserved (AAC encoder may pad a few samples).
    assert sr == 48000
    assert len(samples) >= 48000
    # Content survives the round trip (non-trivial RMS).
    assert np.sqrt(np.mean(samples.astype(np.float64) ** 2)) > 0.01


def test_decode_webm_uses_ffmpeg_fallback():
    import os
    import subprocess
    import tempfile

    exe = ffmpeg_binary()
    assert exe, "ffmpeg binary unavailable"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.wav")
        dst = os.path.join(tmp, "out.webm")
        with open(src, "wb") as fh:
            fh.write(_sine_wav_bytes())
        result = subprocess.run(
            [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-c:a", "libopus", dst],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace")[:300])
        with open(dst, "rb") as fh:
            webm = fh.read()

    samples, sr = decode_audio(webm, "out.webm")
    assert samples.ndim == 1
    assert sr == 48000
    assert np.sqrt(np.mean(samples.astype(np.float64) ** 2)) > 0.01