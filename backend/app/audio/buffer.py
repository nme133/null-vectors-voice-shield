from __future__ import annotations

import numpy as np

from app.core.logging import get_logger

log = get_logger("AUDIO")

TARGET_SAMPLE_RATE = 16000
SPECTRA_WINDOW_SAMPLES = 64600


class RollingAudioBuffer:
    """Maintains a rolling buffer of mono 16 kHz float32 PCM audio.

    Keeps at most ``max_seconds`` of audio (default 10 s).  Incoming chunks
    are appended and old samples are discarded.  The buffer is *not* thread-safe;
    it is owned by a single WebSocket session.
    """

    def __init__(self, sample_rate: int = TARGET_SAMPLE_RATE, max_seconds: int = 10):
        self.sample_rate = sample_rate
        self.max_samples = sample_rate * max_seconds
        self.buffer: np.ndarray = np.empty(0, dtype=np.float32)
        self.total_received: int = 0

    def append(self, samples: np.ndarray) -> None:
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)
        self.buffer = np.concatenate([self.buffer, samples])
        self.total_received += len(samples)
        if len(self.buffer) > self.max_samples:
            self.buffer = self.buffer[-self.max_samples:]
        log.debug("buffer len=%d total=%d", len(self.buffer), self.total_received)

    def get_window(self, n_samples: int = SPECTRA_WINDOW_SAMPLES) -> np.ndarray:
        """Return the most recent *n_samples* samples.

        If fewer samples are available, tile-repeat to fill the window
        (matches the reference evaluation pipeline).
        """
        if len(self.buffer) == 0:
            return np.zeros(n_samples, dtype=np.float32)
        if len(self.buffer) >= n_samples:
            return self.buffer[-n_samples:].copy()
        available = self.buffer.copy()
        repeats = int(n_samples / len(available)) + 1
        tiled = np.tile(available, repeats)[:n_samples]
        return tiled.astype(np.float32)

    def get_segment(self, start_seconds: float, end_seconds: float) -> np.ndarray:
        """Return audio between *start_seconds* and *end_seconds* ago (rolling window)."""
        start_sample = max(0, len(self.buffer) - int(end_seconds * self.sample_rate))
        end_sample = max(0, len(self.buffer) - int(start_seconds * self.sample_rate))
        if end_sample <= start_sample:
            return np.empty(0, dtype=np.float32)
        return self.buffer[start_sample:end_sample].copy()

    def get_new_since(self, total_since: int) -> np.ndarray:
        """Return the samples appended *after* ``total_since`` samples.

        ``total_since`` is measured against ``total_received`` (which never
        shrinks), so this yields exactly the newest audio that has not yet
        been processed — used by the transcription worker to avoid feeding
        Whisper the same rolling window repeatedly.
        """
        if total_since >= self.total_received:
            return np.empty(0, dtype=np.float32)
        newest_count = self.total_received - total_since
        available = min(newest_count, len(self.buffer))
        if available <= 0:
            return np.empty(0, dtype=np.float32)
        return self.buffer[-available:].copy()

    def clear(self) -> None:
        self.buffer = np.empty(0, dtype=np.float32)
        self.total_received = 0

    @property
    def duration_seconds(self) -> float:
        return len(self.buffer) / self.sample_rate

    @property
    def has_enough(self) -> bool:
        return len(self.buffer) >= SPECTRA_WINDOW_SAMPLES
