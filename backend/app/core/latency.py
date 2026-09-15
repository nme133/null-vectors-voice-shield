from __future__ import annotations

import time

from app.core.logging import get_logger

log = get_logger("LATENCY")

# Known pipeline stages (diagnostic reference only).
STAGES = (
    "session_start",
    "audio_received",
    "speech_detected",
    "spectra_started",
    "spectra_finished",
    "whisper_started",
    "whisper_finished",
    "gpt_started",
    "gpt_finished",
    "risk_updated",
    "websocket_sent",
)


class PipelineTiming:
    """Monotonic end-to-end latency instrumentation for one WebSocket session.

    Records ``time.monotonic()`` milestones for each pipeline stage and logs a
    compact line per stage: seconds since the session anchor and seconds since
    the previous recorded stage, so real latency can be traced end to end
    (audio -> speech -> spectra/whisper -> gpt -> risk -> websocket).

    Purely diagnostic: marking never changes behavior or blocks the loop.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._marks: dict[str, float] = {}
        self._previous: float | None = None

    def mark(self, stage: str, detail: str = "") -> float:
        now = time.monotonic()
        self._marks[stage] = now
        anchor = self._marks.get("session_start", now)
        since_anchor = now - anchor
        since_prev = now - self._previous if self._previous is not None else 0.0
        self._previous = now
        line = (
            f"LATENCY session={self.session_id} stage={stage:<18s} "
            f"since_start={since_anchor:7.3f}s since_prev={since_prev:7.3f}s"
        )
        if detail:
            line += f" {detail}"
        log.info(line)
        return now