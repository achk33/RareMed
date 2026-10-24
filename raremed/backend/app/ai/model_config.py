"""Runtime model settings.

`model.json` is the default. Environment variables override individual fields
so a deployment can change the model without editing the file.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

_CONFIG_PATH = Path(__file__).with_name("model.json")
_PROVIDERS = {"ollama", "openai", "vllm"}


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    temperature: float
    num_ctx: int
    think: bool


def load_model_config(settings: Settings) -> ModelConfig:
    raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    provider = (settings.inference_provider or str(raw.get("provider", "ollama"))).strip().lower()
    if provider not in _PROVIDERS:
        provider = "ollama"
    model = (settings.ollama_model or str(raw.get("model", "qwen3:4b"))).strip() or "qwen3:4b"
    temperature = (
        settings.model_temperature
        if settings.model_temperature is not None
        else float(raw.get("temperature", 0.6))
    )
    num_ctx = settings.model_num_ctx if settings.model_num_ctx is not None else int(raw.get("num_ctx", 4096))
    think = settings.ollama_think if settings.ollama_think is not None else bool(raw.get("think", False))
    return ModelConfig(
        provider=provider,
        model=model,
        temperature=min(max(temperature, 0.0), 2.0),
        num_ctx=min(max(num_ctx, 512), 131072),
        think=think,
    )
