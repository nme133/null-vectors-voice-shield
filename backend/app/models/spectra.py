from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    pass

log = get_logger("SPECTRA")

# Window size expected by Spectra-AASIST3 (≈ 4.04 s at 16 kHz)
WINDOW_SAMPLES = 64600

# Default bona-fide threshold from the reference implementation
DEFAULT_THRESHOLD = -1.0625009


class SpectraWrapper:
    """Thin wrapper around the local Spectra-AASIST3 model.

    Handles:
    - Loading from local path or HuggingFace Hub
    - Device selection (CUDA / CPU)
    - Raw inference (returns logits)
    - Score interpretation (bona-fide logit → spoof score for UI)
    """

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.loaded = False
        self.predict_threshold = DEFAULT_THRESHOLD
        # Serializes GPU inference across threads (the WS loop schedules
        # windows via a worker task/executor).
        self._infer_lock = threading.Lock()

    def load(self) -> bool:
        device = settings.device if torch.cuda.is_available() else "cpu"
        self.device = device
        log.info("Loading Spectra-AASIST3 on device=%s", device)

        model_path = settings.spectra_model_path.strip()
        try:
            if model_path and Path(model_path).is_dir():
                self._load_local(model_path)
            else:
                self._load_hub()
            self.model.eval()
            self.model.to(device)
            self.loaded = True
            log.info("Model loaded successfully")
            return True
        except Exception:
            log.exception("Failed to load Spectra-AASIST3")
            self.loaded = False
            return False

    def _load_local(self, path: str) -> None:
        p = Path(path)
        model_py = p / "model.py"
        if not model_py.exists():
            raise FileNotFoundError(f"model.py not found in {path}")

        # Temporarily add directory to sys.path so we can import the model class
        path_str = str(p.resolve())
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

        from model import SpectraAASIST3

        # Try from_pretrained first (uses model.safetensors in the dir)
        try:
            self.model = SpectraAASIST3.from_pretrained(path_str)
            log.info("Loaded via from_pretrained from %s", path)
            return
        except Exception:
            log.debug("from_pretrained failed, trying manual load", exc_info=True)

        # Fallback: create instance + load state dict from safetensors
        try:
            from safetensors.torch import load_file

            self.model = SpectraAASIST3()
            state = load_file(str(p / "model.safetensors"))
            self.model.load_state_dict(state, strict=False)
            log.info("Loaded via safetensors from %s", path)
        except ImportError:
            self.model = SpectraAASIST3()
            # Use torch.load as final fallback
            weights_path = p / "model.safetensors"
            if weights_path.exists():
                from safetensors.torch import load_file
                self.model.load_state_dict(load_file(str(weights_path)), strict=False)
            log.info("Loaded via torch fallback from %s", path)

    def _load_hub(self) -> None:
        from model import SpectraAASIST3

        self.model = SpectraAASIST3.from_pretrained("lab260/Spectra-AASIST3")
        log.info("Loaded from HuggingFace Hub")

    @torch.inference_mode()
    def predict(self, audio_window: np.ndarray) -> dict:
        """Run inference on a single audio window (64600 float32 samples).

        Returns:
            {
                "raw_bonafide_logit": float,   # raw model output for bona-fide class
                "is_spoof": bool,
                "threshold": float,
            }
        """
        if not self.loaded or self.model is None:
            return {"raw_bonafide_logit": 0.0, "is_spoof": True, "threshold": DEFAULT_THRESHOLD}

        with self._infer_lock:
            tensor = torch.from_numpy(audio_window).unsqueeze(0).to(self.device)
            logits = self.model(tensor)
        # Shape: (1, 2) — index 0 = spoof, index 1 = bona-fide
        bonafide_logit = float(logits[0, 1].cpu())
        is_spoof = bonafide_logit < self.predict_threshold

        return {
            "raw_bonafide_logit": bonafide_logit,
            "is_spoof": is_spoof,
            "threshold": self.predict_threshold,
        }

    def unload(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.loaded = False
        log.info("Model unloaded")


# Global singleton
spectra = SpectraWrapper()
