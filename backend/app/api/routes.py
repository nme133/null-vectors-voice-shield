from __future__ import annotations

import torch
from fastapi import APIRouter

from app.core.config import settings
from app.models.spectra import spectra

router = APIRouter()


@router.get("/health")
async def health():
    device = settings.device if torch.cuda.is_available() else "cpu"
    gpu_name = ""
    if torch.cuda.is_available():
        try:
            gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            gpu_name = "unknown"

    return {
        "status": "ok",
        "device": device,
        "gpu": gpu_name,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "spectra_loaded": spectra.loaded,
        "demo_mode": settings.demo_mode,
    }
