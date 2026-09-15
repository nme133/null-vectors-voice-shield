import numpy as np

from app.audio.processing import (
    detect_speech,
    apply_preemphasis,
    prepare_for_spectra,
    resample,
    to_mono,
)


def test_to_mono_stereo():
    stereo = np.zeros((2, 1000), dtype=np.float32)
    stereo[0, :] = 0.5
    stereo[1, :] = -0.5
    mono = to_mono(stereo)
    assert mono.shape == (1000,)
    assert np.allclose(mono, 0.0)


def test_resample_identity_same_rate():
    audio = np.random.randn(1000).astype(np.float32)
    out = resample(audio, 48000, 48000)
    assert np.array_equal(out, audio)


def test_resample_48000_to_16000_length():
    audio = np.random.randn(4800).astype(np.float32)
    out = resample(audio, 48000, 16000)
    assert len(out) == 1600  # rate /4


def test_resample_downsample_is_temperature_of_input():
    # A constant signal must stay constant after resampling
    audio = np.full(1000, 0.7, dtype=np.float32)
    out = resample(audio, 48000, 24000)
    assert np.allclose(out, 0.7, atol=1e-5)


def test_preemphasis_shape_preserved():
    audio = np.ones(100, dtype=np.float32)
    out = apply_preemphasis(audio, coeff=0.97)
    assert out.shape == audio.shape
    assert np.allclose(out[1:], 0.03)


def test_prepare_for_spectra_output_shape():
    audio = np.random.randn(4800).astype(np.float32)
    out = prepare_for_spectra(audio, sample_rate=48000)
    assert out.shape == (64600,)
    assert out.dtype == np.float32


def test_prepare_truncates_long_audio():
    long_audio = np.random.randn(160000).astype(np.float32)
    out = prepare_for_spectra(long_audio, sample_rate=16000)
    assert out.shape == (64600,)


def test_detect_speech_rejects_digital_silence():
    silence = np.zeros(64600, dtype=np.float32)
    assert detect_speech(silence, sample_rate=16000) is False


def test_detect_speech_rejects_quiet_noise():
    noise = np.random.uniform(-1e-4, 1e-4, 64600).astype(np.float32)
    assert detect_speech(noise, sample_rate=16000) is False


def test_detect_speech_accepts_sustained_speech_energy():
    ton = np.sin(2 * np.pi * 220 * np.arange(64600) / 16000).astype(np.float32) * 0.3
    assert detect_speech(ton, sample_rate=16000) is True


def test_detect_speech_rejects_brief_noise_blip():
    # A ~100 ms burst of loud noise in an otherwise silent window is NOT
    # speech — the gate must require >300 ms of active signal.
    window = np.zeros(64600, dtype=np.float32)
    blip_len = int(0.1 * 16000)
    window[:blip_len] = 0.9
    assert detect_speech(window, sample_rate=16000) is False


def test_detect_speech_accepts_short_utterance_embedded_in_silence():
    # ~1.2 s of speech-like energy inside a mostly silent 4 s window should
    # pass the gate (well above the 300 ms minimum).
    window = np.zeros(64600, dtype=np.float32)
    start = int(0.5 * 16000)
    speech_len = int(1.2 * 16000)
    t = np.arange(speech_len) / 16000
    window[start:start + speech_len] = 0.3 * np.sin(2 * np.pi * 180 * t)
    assert detect_speech(window, sample_rate=16000) is True