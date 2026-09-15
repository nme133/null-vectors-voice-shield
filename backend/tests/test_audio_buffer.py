import numpy as np

from app.audio.buffer import RollingAudioBuffer


def test_buffer_appends_and_retains():
    buf = RollingAudioBuffer(sample_rate=16000, max_seconds=2)
    chunk = np.ones(8000, dtype=np.float32)
    buf.append(chunk)
    assert buf.duration_seconds == 0.5
    assert buf.total_received == 8000


def test_buffer_truncates_oldest():
    buf = RollingAudioBuffer(sample_rate=16000, max_seconds=1)
    buf.append(np.ones(16000, dtype=np.float32))     # fill exactly
    buf.append(np.ones(16000, dtype=np.float32))     # overflow
    assert len(buf.buffer) == 16000


def test_get_window_tiles_short_audio():
    buf = RollingAudioBuffer()
    short = np.ones(16000, dtype=np.float32)
    buf.append(short)
    window = buf.get_window(64600)
    assert window.shape == (64600,)
    assert np.all(window == 1.0)


def test_get_window_uses_recent_samples():
    buf = RollingAudioBuffer()
    buf.append(np.zeros(16000, dtype=np.float32))
    buf.append(np.ones(16000, dtype=np.float32))
    window = buf.get_window(16000)
    assert np.all(window == 1.0)


def test_buffer_clear():
    buf = RollingAudioBuffer()
    buf.append(np.ones(1000, dtype=np.float32))
    buf.clear()
    assert len(buf.buffer) == 0
    assert buf.total_received == 0


def test_get_new_since_returns_only_unprocessed_audio():
    buf = RollingAudioBuffer()
    buf.append(np.zeros(16000, dtype=np.float32))
    cursor = buf.total_received
    buf.append(np.ones(16000, dtype=np.float32))

    new_audio = buf.get_new_since(cursor)
    assert len(new_audio) == 16000
    assert np.all(new_audio == 1.0)


def test_get_new_since_empty_when_cursor_caught_up():
    buf = RollingAudioBuffer()
    buf.append(np.ones(16000, dtype=np.float32))
    cursor = buf.total_received
    assert buf.get_new_since(cursor).size == 0


def test_get_new_since_respects_rolling_limit():
    buf = RollingAudioBuffer(max_seconds=1)
    buf.append(np.ones(16000, dtype=np.float32))
    cursor = 0  # pretend we processed nothing; only the retained tail exists
    newest = buf.get_new_since(cursor)
    assert len(newest) <= 16000
    assert np.all(newest == 1.0)