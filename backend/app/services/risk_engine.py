from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.logging import get_logger

log = get_logger("RISK")

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Bona-fide threshold used by Spectra-AASIST3 (raw class-1 logit cutoff).
SPECTRA_THRESHOLD = -1.0625009
# Logit at or below this is treated as a strong spoof (max severity).
STRONG_SPOOF_LOGIT = -4.0
# Any confirmed spoof contributes at least this; strong spoofs reach VOICE_MAX.
VOICE_FLOOR = 15.0
VOICE_MAX = 40.0
# A single, un-confirmed sub-threshold logit reading (streak not yet high
# enough to declare "spoof") can move the gauge via a continuous, evidence
# based disposition reading.  It is capped just below the MEDIUM boundary (30)
# so a strong-but-unconfirmed spoof signal visibly moves the gauge toward the
# evidence before the 3-window verdict commits, while one noisy window can
# still NEVER alone escalate the call to MEDIUM.
STREAM_VOICE_MAX = 20.0


def spoof_severity(bonafide_logit: float) -> float:
    """Map how far below the bona-fide threshold a logit sits (0-1).

    Values at/above the threshold score 0; strong spoofs (≤ STRONG_SPOOF_LOGIT)
    score 1. This is a monotonic severity measure, *not* a probability.
    """
    if bonafide_logit >= SPECTRA_THRESHOLD:
        return 0.0
    if bonafide_logit <= STRONG_SPOOF_LOGIT:
        return 1.0
    return (SPECTRA_THRESHOLD - bonafide_logit) / (SPECTRA_THRESHOLD - STRONG_SPOOF_LOGIT)


def classify_level(score: int) -> str:
    if score < 30:
        return "LOW"
    if score < 60:
        return "MEDIUM"
    if score < 80:
        return "HIGH"
    return "CRITICAL"


def score_to_display(logit: float, *, threshold: float = SPECTRA_THRESHOLD) -> float:
    """Map a raw bona-fide logit to a 0-100 spoof display index.

    Anchored to the model's own bona-fide threshold: at the threshold the index
    reads 50, clearly-human high logits read low (4), strong spoof logits
    (<= STRONG_SPOOF_LOGIT) read high (96).  The index is a normalized
    signal-strength readout derived consistently from the actual Spectra
    signal — it is NOT a probability.  The raw bonafide logit is always
    preserved separately for consumers.
    """
    if logit <= STRONG_SPOOF_LOGIT:
        return 96.0
    if logit >= 4.0:
        return 4.0
    if logit >= threshold:
        frac = (logit - threshold) / (4.0 - threshold)
        return 50.0 - frac * 46.0
    frac = (threshold - logit) / (threshold - STRONG_SPOOF_LOGIT)
    return 50.0 + frac * 46.0


@dataclass
class RiskSnapshot:
    risk_score: int = 0
    risk_level: str = "LOW"
    voice_component: float = 0.0
    social_component: float = 0.0
    action_component: float = 0.0
    reasons: list[str] = field(default_factory=list)
    recommendation: str = ""
    timestamp: float = field(default_factory=time.monotonic)


class RiskEngine:
    """Deterministic, explainable risk engine with temporal smoothing.

    Additive scoring model (the total is exactly the sum of its parts):

      - Voice spoof / voice-authenticity signal:  0-40 points
      - Conversation / social engineering signals: 0-40 points
      - High-risk actions (financial / OTP / credentials): 0-20 points
      - TOTAL = 0-100 → LOW / MEDIUM / HIGH / CRITICAL

    The three channels are INDEPENDENT evidence sources.  A human-sounding
    voice contributes 0 acoustic points but the conversation channel can still
    drive the total up on its own (e.g. a confirmed transfer + pressure +
    secrecy reaches MEDIUM/HIGH with zero voice points).  Conversely a
    suspicious voice with a completely normal conversation raises the total
    via the voice channel alone but never to CRITICAL.

    Conversation channel weighting (deterministic, per-signal inspectable):
      - social engineering (0-40):   urgency·9 + authority·10 + financial·9
                                     + secrecy·8 + persuasion·8
                                     + repeated_confirmation·7 + threat·6
      - high-risk actions (0-20):    financial·8.5 + credential·6.5 + otp·5

    Voice points come ONLY from the actual Spectra bona-fide logit:
      - a confirmed spoof contributes a minimum of VOICE_FLOOR, scaling with
        severity up to VOICE_MAX;
      - an un-confirmed sub-threshold logit contributes a small disposition
        reading (≤ STREAM_VOICE_MAX, cannot exceed LOW alone).
    Merely hearing a human speak contributes nothing — talking is not risk.

    Conversation points are gained only from detected signals (urgency,
    authority impersonation, financial action/pressure, secrecy, persuasion,
    repeated-confirmation pressure, credential/OTP asks, threat).  A transcript
    that exists but contains no manipulation signals contributes 0.  A missing
    or failed analysis contributes nothing — it can never erase evidence that
    an earlier conversation already established (the WebSocket layer merges
    analysis into session state instead of overwriting it).

    The score is a raw fusion of evidence, NOT a probability.

    Temporal smoothing uses an asymmetric exponential moving average: rises are
    followed quickly (persistent evidence escalates), falls are damped so a
    single clean frame cannot drop an established HIGH/CRITICAL call to LOW.
    Every call releases the freshly-smoothed score — there is no separate
    hard freeze, so the displayed risk always corresponds to the current
    evidence instead of being pinned to a stale number until a large enough
    change accumulates.  False alarms are still prevented by the voice streak
    (a verdict needs 3 consistent windows) and by the asymmetric EMA itself.
    """

    EMA_RISE_ALPHA = 0.9  # how quickly the score reflects rising risk (e.g. fresh GPT evidence)
    EMA_DECAY_ALPHA = 0.2  # how slowly it falls when risk drops (avoid jittery flicker)

    def __init__(self):
        self._prev_score: float = 0.0
        self._prev_level: str = "LOW"
        self._initialized: bool = False

    def compute(
        self,
        is_spoof: bool,
        bonafide_logit: float,
        conversation_signals: dict,
    ) -> RiskSnapshot:
        """Compute a single risk snapshot from current signals.

        ``bonafide_logit`` is the (ideally smoothed) Spectra raw class-1 logit:
        higher = more bona-fide-like, lower = more spoof-like.  ``is_spoof`` is
        the temporally-consistent verdict produced by the voice pipeline (only
        after several consecutive below-threshold windows agree).
        """
        reasons: list[str] = []

        # --- Voice component (0-40) ---
        voice_score = self._voice_component(bonafide_logit, is_spoof, reasons)

        # --- Social engineering component (0-40) ---
        social_score = self._social_component(conversation_signals, reasons)

        # --- High-risk action component (0-20) ---
        action_score = self._action_component(conversation_signals, reasons)

        # --- Fusion: plain sum of the three bounded channels, clamped to 100.
        raw_total = voice_score + social_score + action_score
        raw_total = max(0.0, min(100.0, raw_total))

        # --- Temporal smoothing ---
        smoothed = self._smooth(raw_total)
        final_score = int(round(smoothed))
        final_score = max(0, min(100, final_score))
        level = classify_level(final_score)

        self._prev_score = final_score
        self._prev_level = level
        self._initialized = True

        recommendation = self._recommendation(final_score, level, is_spoof, conversation_signals)

        snapshot = RiskSnapshot(
            risk_score=final_score,
            risk_level=level,
            voice_component=voice_score,
            social_component=social_score,
            action_component=action_score,
            reasons=reasons,
            recommendation=recommendation,
        )

        log.info(
            "Risk: score=%d level=%s voice=%.1f social=%.1f action=%.1f",
            final_score, level, voice_score, social_score, action_score,
        )
        return snapshot

    def reset(self) -> None:
        self._prev_score = 0.0
        self._prev_level = "LOW"
        self._initialized = False

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _voice_component(
        self, bonafide_logit: float, is_spoof: bool, reasons: list[str]
    ) -> float:
        """Map the acoustic authenticity signal to 0-40 risk points.

        Anchored to the model's own bona-fide threshold (higher logit = more
        bona-fide-like).
          - Bona-fide voice (logit ≥ threshold) → 0 points. Hearing a human
            speak is NOT risk.
          - Un-confirmed live reading → a small disposition reading bounded by
            STREAM_VOICE_MAX (< MEDIUM), scaled by how far the current logit
            sits below the threshold.  This lets the gauge react to the live
            buffer without a single window alone elevating severity.
          - Confirmed spoof → VOICE_FLOOR minimum, scaling with severity up to
            VOICE_MAX.  Score is a severity weight, *not* a probability.
        """
        if not is_spoof and bonafide_logit >= SPECTRA_THRESHOLD:
            return 0.0

        depth = spoof_severity(bonafide_logit)

        if is_spoof:
            reasons.append("Possible synthetic/ cloned voice detected")

            severity = spoof_severity(bonafide_logit)
            score = VOICE_FLOOR + severity * (VOICE_MAX - VOICE_FLOOR)
            score = max(VOICE_FLOOR, min(VOICE_MAX, score))

            if score > 30:
                reasons.append("Strong acoustic spoof indicators")
            elif score > 20:
                reasons.append("Moderate acoustic anomalies in voice")

            return score

        # Un-confirmed, sub-threshold logit: continuous streaming disposition.
        live = STREAM_VOICE_MAX * min(1.0, depth)

        if depth > 0.5:
            reasons.append("Suspicious acoustic anomalies in voice")

        return live

    def _social_component(self, signals: dict, reasons: list[str]) -> float:
        """Map detected conversation signals to 0-40 social engineering points.

        Only signals actually present in the conversation analysis contribute;
        a transcript with no manipulation signals scores 0.  A field that is
        missing or invalid is treated as absent (contributes 0 for this term)
        — but absence here never overwrites the session state, so previously
        established evidence is preserved.
        """
        urgency = self._num(signals, "urgency")
        authority = self._num(signals, "authority_impersonation")
        financial = self._num(signals, "financial_request")
        threat = self._num(signals, "threat")
        secrecy = self._num(signals, "secrecy")
        persuasion = self._num(signals, "persuasion")
        repeated = self._num(signals, "repeated_confirmation")

        # Weighted combination (deterministic; inspectable per signal).
        # Channel cap 40: several coincident, strong signals saturate the
        # social-engineering channel instead of topping out in LOW.
        score = (
            urgency * 9.0
            + authority * 10.0
            + financial * 9.0
            + secrecy * 8.0
            + persuasion * 8.0
            + repeated * 7.0
            + threat * 6.0
        )
        score = max(0.0, min(40.0, score))

        if authority > 0.5:
            reasons.append("Caller impersonates authority or institution")
        if urgency > 0.5:
            reasons.append("High urgency/time-pressure tactics detected")
        if threat > 0.5:
            reasons.append("Threatening or intimidating language detected")
        if financial > 0.5:
            reasons.append("Suspicious financial request detected")
        if secrecy > 0.5:
            reasons.append("Caller discourages discussion of the transaction")
        if persuasion > 0.5:
            reasons.append("Trust/persuasion pressure detected")
        if repeated > 0.5:
            reasons.append("Repeated confirmation requests detected")
        if urgency > 0.5 and financial > 0.5:
            reasons.append("Urgent financial action detected")

        return score

    def _action_component(self, signals: dict, reasons: list[str]) -> float:
        """Map high-risk conversational actions to 0-20 points."""
        financial = self._num(signals, "financial_request")
        credential = self._num(signals, "credential_request")
        otp = self._num(signals, "otp_request")
        repeated = self._num(signals, "repeated_confirmation")

        score = (
            financial * 8.5
            + credential * 6.5
            + otp * 5.0
        )
        score = max(0.0, min(20.0, score))

        if otp > 0.3:
            reasons.append("OTP or verification code requested")
        if credential > 0.3:
            reasons.append("Login credentials or account info requested")
        if financial > 0.7:
            reasons.append("Explicit fund transfer instruction detected")
        if financial > 0.5 and repeated > 0.5:
            reasons.append("Caller is pressuring the user to confirm a transfer")

        return score

    @staticmethod
    def _num(signals: dict, key: str) -> float:
        """Read a signal as a clamped [0,1] float; missing/invalid -> 0.

        An absent field contributes zero for THIS term only.  Callers must not
        use this helper as justification for erasing stored evidence — the
        WebSocket session state preserves strong prior readings when a newer
        analysis omits a field.
        """
        try:
            val = signals.get(key, 0.0)
            if isinstance(val, bool):
                return 1.0 if val else 0.0
            val = float(val)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, val))

    def _smooth(self, raw: float) -> float:
        """Asymmetric exponential moving average.

        Rises are followed quickly (freshly confirmed evidence must move the
        score up promptly); falls are damped so a single clean frame can't
        drop a HIGH/CRITICAL call back to LOW.
        """
        if not self._initialized:
            return raw
        if raw > self._prev_score:
            return self.EMA_RISE_ALPHA * raw + (1.0 - self.EMA_RISE_ALPHA) * self._prev_score
        return self.EMA_DECAY_ALPHA * raw + (1.0 - self.EMA_DECAY_ALPHA) * self._prev_score

    def _recommendation(
        self, score: int, level: str, is_spoof: bool, signals: dict
    ) -> str:
        if level == "CRITICAL":
            return "DO NOT transfer funds or share information. Terminate call immediately and verify independently."
        if level == "HIGH":
            return "Exercise extreme caution. Do not comply with requests. Independently verify the caller."
        if level == "MEDIUM":
            return "Proceed with caution. Verify caller identity through official channels."
        return "Call appears normal. Continue monitoring."


# Global singleton
risk_engine = RiskEngine()