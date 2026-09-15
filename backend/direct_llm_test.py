import asyncio
import json

from app.services.conversation import conversation_service
from app.core.config import settings


async def main():
    transcript = (
        "Hello, I am calling from your bank. Your account has a serious problem. "
        "You need to transfer the money immediately. Send me the OTP so I can "
        "complete the transaction. Do not call the bank because this needs to be "
        "handled right now."
    )
    print("=" * 60)
    print("[LLM TRACE] DIRECT TEST START")
    print("API_KEY set:", bool(settings.groq_api_key))
    print("MODEL:", settings.groq_chat_model)
    print("DEMO_MODE:", settings.demo_mode)
    print("[LLM TRACE] TRANSCRIPT RECEIVED:")
    print(transcript)
    print("=" * 60)

    result = await conversation_service.analyze(transcript)

    print("=" * 60)
    print("[LLM TRACE] LLM PARSED:")
    print(json.dumps(result, indent=2))
    print("=" * 60)

    checks = {
        "financial_request": result.get("financial_request", 0) > 0,
        "credential_request": result.get("credential_request", 0) > 0,
        "urgency": result.get("urgency", 0) > 0,
        "authority_impersonation": result.get("authority_impersonation", 0) > 0,
        "otp_request": result.get("otp_request", 0) > 0,
    }
    print("PASS/FAIL:", json.dumps(checks, indent=2))
    overall = all(checks.values())
    print("OVERALL:", "PASS" if overall else "FAIL")


asyncio.run(main())