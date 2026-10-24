"""Ollama reachability for status responses.

Generation lives in the provider package. This wrapper only reports whether
the configured model is installed.
"""

from app.ai.providers.ollama import OllamaProvider
from app.schemas.status import OllamaStatus


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def probe(self, configured_model: str = "", *, think: bool = False) -> OllamaStatus:
        result = OllamaProvider(self.base_url, probe_timeout=self.timeout_seconds).probe(configured_model)
        return OllamaStatus(
            status="ok" if result.reachable else "unavailable",
            base_url=result.base_url,
            detail=result.detail,
            models=result.installed_models,
            configured_model=configured_model,
            model_ready=result.model_ready,
            think=think,
        )
