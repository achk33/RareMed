"""Select the configured inference backend."""

from app.ai.model_config import ModelConfig
from app.ai.providers.base import InferenceProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import Settings


def build_provider(settings: Settings, config: ModelConfig) -> InferenceProvider:
    if config.provider == "openai":
        return OpenAICompatibleProvider("openai", settings.openai_base_url, settings.openai_api_key)
    if config.provider == "vllm":
        return OpenAICompatibleProvider("vllm", settings.vllm_base_url, settings.vllm_api_key)
    return OllamaProvider(settings.ollama_base_url, probe_timeout=settings.ollama_timeout_seconds)
