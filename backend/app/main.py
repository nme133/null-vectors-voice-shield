from __future__ import annotations

import torch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as routes_router
from app.api.uploads import router as uploads_router
from app.api.websocket import router as ws_router
from app.core.config import settings
from app.core.logging import get_logger
from app.models.spectra import spectra

log = get_logger("SERVER")


def _report_hardware() -> None:
    cuda_available = torch.cuda.is_available()
    gpu_name = ""
    if cuda_available:
        try:
            gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            gpu_name = "unknown"

    selected = settings.device if cuda_available else "cpu"
    log.info("PyTorch version: %s", torch.__version__)
    log.info("CUDA available: %s", cuda_available)
    if gpu_name:
        log.info("GPU: %s", gpu_name)
    log.info("Device: %s", selected)
    if settings.demo_mode:
        log.info("DEMO MODE is ENABLED — simulated events, no real inference")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice Shield Backend",
        description="AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_router)
    app.include_router(ws_router)
    app.include_router(uploads_router)

    @app.on_event("startup")
    async def _startup():
        log.info("Starting Voice Shield backend")
        _report_hardware()
        spectra.load()

    @app.on_event("shutdown")
    async def _shutdown():
        log.info("Shutting down Voice Shield backend")
        spectra.unload()

    return app


app = create_app()