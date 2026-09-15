from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("LLM")

# All signal keys the analyzer may return, in a stable order (used for logging
# and for merge bookkeeping in the WebSocket session state).
SIGNAL_FIELDS = (
    "urgency",
    "authority_impersonation",
    "financial_request",
    "credential_request",
    "otp_request",
    "threat",
    "secrecy",
    "persuasion",
    "repeated_confirmation",
)

# gpt-oss-120b is a REASONING model on Groq: it spends a large part of the token
# budget on its chain-of-thought BEFORE emitting the JSON answer.  The old
# 512-token budget starved it — the model burned every token on `reasoning` and
# returned an EMPTY `content` string, which the parser rejected, so the
# conversation analysis silently produced nothing and the Analysis tab stayed at
# "AWAITING SPEECH TRANSCRIPT".  4096 gives the model room for reasoning plus a
# complete JSON answer.  gpt-oss-120b is a larger frontier reasoning model, so
# JSON mode is enabled to guarantee a parser-able JSON object every time.
ANALYSIS_MAX_TOKENS = 4096

ANALYSIS_SYSTEM_PROMPT = """You are a real-time voice-call security analyst.

Your job is to detect conversational indicators associated with impersonation scams, social engineering, financial fraud, credential theft, manipulation, and attempts to bypass independent verification.

Analyze ONLY the transcript provided.

Do not claim that the caller is definitely malicious.

Return ONLY valid JSON.

Detect:

- urgency
- authority impersonation
- financial requests
- credential/OTP requests
- threats
- secrecy
- verification bypass
- high-risk actions
- social engineering

Be conservative from a SECURITY perspective.

Treat each of these as strong risk indicators:
money transfers, payment requests, bank/account actions, requests for sensitive
information, OTP requests, passwords, PINs, authentication codes, instructions
to disable or bypass security, asset release without independent verification,
authority impersonation, urgency, threats, secrecy, and social engineering.

A request involving money, transfers, payments, bank accounts, OTPs, passwords,
PINs, authentication codes, or other sensitive actions should receive a strong
risk signal.

Financial requests should produce a strong financial_request signal.

Combinations such as:

financial request + urgency
financial request + authority impersonation
financial request + secrecy
financial request + verification bypass
financial request + OTP/credential request

should substantially increase the conversational risk.

Example signal mappings:

"Please transfer 50000."                                    → strong financial_request
"Transfer it immediately."                                  → financial_request + urgency
"I'm calling from your bank. Transfer the money immediately."
                                                            → financial_request + authority_impersonation + urgency
"Send me the OTP so I can complete the transfer."           → financial_request + credential_request
"Transfer the money now. Don't tell anyone and don't call
the bank."                                                  → financial_request + urgency + secrecy + verification_bypass

Report risk indicators only. Never claim that the caller is
definitely a scammer.

Return:

{
  "urgency": 0.0,
  "authority_impersonation": 0.0,
  "financial_request": 0.0,
  "credential_request": 0.0,
  "threat": 0.0,
  "secrecy": 0.0,
  "verification_bypass": 0.0,
  "high_risk_action": 0.0,
  "social_engineering": 0.0,
  "risk_reasons": [],
  "recommendation": ""
}

All numeric values must be between 0.0 and 1.0.

Do not output markdown.
Do not output ```json.
Return JSON only."""

# Values returned when the model/API produced nothing usable (NO evidence).
# These must never be interpreted as "evidence of safety".
EMPTY_RESULT: dict[str, Any] = {}


class ConversationAnalysisService:
    """Analyzes transcripts for social-engineering signals via Groq GPT-OSS.

    The analysis result is a *partial* dict: only fields the model actually
    returned are present. Missing / invalid fields are NOT forced to 0.0 —
    downstream merges new evidence over the session state so an empty or weak
    response cannot zero out strong evidence from an earlier transcript.
    """

    DEFAULT_RESULT: dict[str, Any] = {
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

    async def analyze(self, transcript_text: str) -> dict:
        if settings.demo_mode:
            log.info("GPT-OSS SKIPPED: demo mode active")
            return EMPTY_RESULT.copy()

        api_key = settings.groq_api_key
        if not api_key:
            log.error("GPT-OSS ERROR: GROQ_API_KEY not configured")
            return EMPTY_RESULT.copy()

        if not transcript_text.strip():
            log.warning("GPT-OSS ERROR: empty transcript received")
            return EMPTY_RESULT.copy()

        log.info("[LLM TRACE] TRANSCRIPT RECEIVED:")
        log.info("%s", transcript_text.strip())
        log.info("[LLM TRACE] MODEL: %s", settings.groq_chat_model)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    settings.groq_chat_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.groq_chat_model,
                        "messages": [
                            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                            {"role": "user",
                             "content": f"Analyze this live call transcript:\n\n{transcript_text}"},
                        ],
                        "temperature": 0.0,
                        "max_tokens": ANALYSIS_MAX_TOKENS,
                        "response_format": {"type": "json_object"},
                    },
                )
        except Exception as exc:
            log.error("[LLM TRACE] GROQ ERROR: %r", exc)
            raise

        if response.status_code != 200:
            log.error("GPT-OSS ERROR: HTTP %d: %s",
                      response.status_code, response.text[:500])
            return EMPTY_RESULT.copy()

        try:
            choice = response.json()["choices"][0]
        except (KeyError, IndexError, ValueError):
            log.error("GPT-OSS ERROR: unexpected response shape: %s",
                      response.text[:500])
            return EMPTY_RESULT.copy()

        content = choice.get("message", {}).get("content") or ""
        if not content.strip():
            # A reasoning model can burn its whole budget on chain-of-thought
            # and emit no answer.  NEVER pretend the LLM ran.
            log.error("GPT-OSS ERROR: empty content from %s (finish_reason=%s). "
                      "Raise ANALYSIS_MAX_TOKENS.",
                      settings.groq_chat_model, choice.get("finish_reason"))
            return EMPTY_RESULT.copy()

        log.info("[LLM TRACE] GROQ RESPONSE RECEIVED")
        log.info("[LLM TRACE] RAW: %s", content.strip())

        result = self._parse_response(content)
        if not result:
            log.error("[LLM TRACE] GROQ ERROR: no usable signals parsed from model output: %s",
                      content.strip()[:2000])
            return EMPTY_RESULT.copy()

        log.info("[LLM TRACE] LLM PARSED: %s reasons=%d",
                 " ".join(f"{k}={result.get(k, '-')}" for k in SIGNAL_FIELDS),
                 len(result.get("reasons", [])))
        return result

    def _parse_response(self, content: str) -> dict:
        """Robustly parse LLM JSON output.

        Accepts BOTH the current GPT-OSS output contract (urgency /
        authority_impersonation / financial_request / credential_request / threat
        / secrecy / verification_bypass / high_risk_action / social_engineering /
        risk_reasons / recommendation) AND the legacy schema, mapping the new
        fields into the legacy signal schema the dashboard and risk engine
        consume (no frontend/engine schema change required).

        Returns a PARTIAL dict containing only fields the model actually
        provided with valid values. Invalid/missing numeric fields are
        dropped (not silently forced to 0.0) so callers can merge evidence
        instead of erasing it.
        """
        result: dict[str, Any] = {}
        try:
            cleaned = content.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                log.warning("GPT-OSS ERROR: non-JSON-object output: %s", content[:200])
                return result

            # Legacy schema fields.
            for key in SIGNAL_FIELDS:
                val = self._coerce_score(parsed.get(key))
                if val is not None:
                    result[key] = val

            conf = self._coerce_score(parsed.get("confidence"))
            if conf is not None:
                result["confidence"] = conf

            # Current GPT-OSS output contract → map into the legacy schema:
            #   - verification_bypass → otp_request (high-risk / OTP grab)
            #   - social_engineering  → persuasion  (umbrella manipulation pressure)
            vb = self._coerce_score(parsed.get("verification_bypass"))
            if vb is not None:
                result["otp_request"] = max(vb, float(result.get("otp_request", 0.0)))

            se = self._coerce_score(parsed.get("social_engineering"))
            if se is not None:
                result["persuasion"] = max(se, float(result.get("persuasion", 0.0)))

            hra = self._coerce_score(parsed.get("high_risk_action"))
            if hra is not None and hra > 0.5:
                result["high_risk_action"] = hra

            # Reasons: legacy `reasons` list plus the new contract's `risk_reasons`.
            reasons = parsed.get("reasons") or []
            if not isinstance(reasons, list):
                reasons = []
            risk_reasons = parsed.get("risk_reasons") or []
            if isinstance(risk_reasons, list):
                reasons = list(reasons) + list(risk_reasons)

            cleaned_reasons: list[str] = []
            seen: set[str] = set()
            for r in reasons:
                if isinstance(r, str) and r.strip() and r.strip() not in seen:
                    seen.add(r.strip())
                    cleaned_reasons.append(r.strip())
            if cleaned_reasons:
                result["reasons"] = cleaned_reasons[:15]

            if not result:
                log.warning("GPT-OSS ERROR: response had no usable fields: %s",
                            content[:200])
                return result

            return result

        except (json.JSONDecodeError, ValueError, TypeError):
            log.error("GPT-OSS ERROR: malformed JSON from model: %s", content[:2000])
            return result

    @staticmethod
    def _coerce_score(value: Any) -> float | None:
        """Return a clamped [0,1] float or None when the value is unusable."""
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            try:
                val = float(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, min(1.0, val))
        return None


conversation_service = ConversationAnalysisService()