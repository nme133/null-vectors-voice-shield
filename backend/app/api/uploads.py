from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.audio.decoder import ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.core.logging import get_logger
from app.models.spectra import spectra
from app.services.file_analysis import file_analysis_pipeline

log = get_logger("UPLOAD")

router = APIRouter()

_ACCEPTED_HINT = ", ".join(sorted(ACCEPTED_EXTENSIONS))


@router.post("/api/v1/analyze/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    language: str = Form("auto"),
):
    """Analyze an uploaded audio file through the REAL backend pipeline.

    The multipart form carries the audio file plus the selected Whisper
    language (ISO-639-1 code, or "auto").  The response is a newline-delimited
    JSON stream (media type ``application/x-ndjson``): one ``stage`` event per
    pipeline stage with real elapsed-time, and a final ``result`` object, or an
    ``error`` event if the pipeline fails.

    Stages re-use the exact same backend singletons as the live WebSocket
    path — no second implementation of Spectra / Whisper / GPT-OSS / risk.
    """
    filename = (file.filename or "").strip()
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = f".{suffix}" if suffix else ""
    if ext and ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted formats: {_ACCEPTED_HINT}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(data)} bytes exceeds the {MAX_UPLOAD_BYTES} byte limit",
        )

    if not spectra.loaded:
        raise HTTPException(
            status_code=503,
            detail="Spectra-AASIST3 model is not loaded — voice analysis unavailable",
        )

    async def gen():
        try:
            async for event in file_analysis_pipeline.stream(data, filename, language):
                yield json.dumps(event) + "\n"
        except Exception as exc:
            log.exception("Upload analysis failed for %r", filename)
            yield json.dumps({
                "type": "error",
                "message": str(exc)[:500] or "Analysis failed",
                "code": "ANALYSIS_ERROR",
            }) + "\n"

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )