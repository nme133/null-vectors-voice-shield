from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_chat_model: str = "openai/gpt-oss-120b"
    spectra_model_path: str = ""
    device: str = "cuda"
    host: str = "0.0.0.0"
    port: int = 8000
    demo_mode: bool = False
    # Seconds of NEW audio between Spectra inference runs. Defaults to one
    # audio chunk (1 s) so overlapping 64.6 k-sample windows re-score freshly
    # appended audio. Raise it if GPU load makes a 1 s cadence unusable.
    spectra_hop_seconds: float = 1.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def groq_api_url(self) -> str:
        return "https://api.groq.com/openai/v1/audio/transcriptions"

    @property
    def groq_chat_url(self) -> str:
        return "https://api.groq.com/openai/v1/chat/completions"


settings = Settings()
