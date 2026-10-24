"""OpenAI-compatible streaming chat.

vLLM exposes this same `/chat/completions` API, so both providers share the
client and differ only by name and base URL.
"""

import json
import logging
import threading
from collections.abc import Callable, Iterator

import httpx

from app.ai.providers.base import GenerationChunk, ProviderError, ProviderProbe
from app.ai.providers.ollama import STREAM_TIMEOUT

logger = logging.getLogger("raremed.inference")


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=STREAM_TIMEOUT))

    def probe(self, model: str) -> ProviderProbe:
        if not self.base_url:
            return ProviderProbe(
                name=self.name,
                model=model,
                base_url="",
                reachable=False,
                model_ready=False,
                detail="not_configured",
            )
        headers = _headers(self.api_key)
        try:
            response = httpx.get(f"{self.base_url}/models", headers=headers, timeout=2.0)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("inference probe failed", extra={"error_type": exc.__class__.__name__})
            return ProviderProbe(
                name=self.name,
                model=model,
                base_url=self.base_url,
                reachable=False,
                model_ready=False,
                detail=exc.__class__.__name__,
            )
        names: list[str] = []
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    names.append(item["id"])
                if len(names) == 20:
                    break
        return ProviderProbe(
            name=self.name,
            model=model,
            base_url=self.base_url,
            reachable=True,
            model_ready=not names or model in names,
            installed_models=names,
        )

    def stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        num_ctx: int,
        think: bool,
        cancel: threading.Event,
    ) -> Iterator[GenerationChunk]:
        del num_ctx, think
        if not self.base_url:
            raise ProviderError(
                "provider_not_configured",
                f"The {self.name} provider has no base URL.",
            )
        if cancel.is_set():
            return
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        client = self._client_factory()
        try:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=_headers(self.api_key),
            ) as response:
                if response.status_code >= 400:
                    raise ProviderError("generation_failed", f"The {self.name} provider rejected the chat request.")
                for line in response.iter_lines():
                    if cancel.is_set():
                        return
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        yield GenerationChunk(done=True)
                        return
                    yield _chunk_from_data(data)
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("inference stream failed", extra={"error_type": exc.__class__.__name__})
            raise ProviderError(
                "ollama_unavailable" if self.name == "ollama" else "generation_failed",
                f"The {self.name} provider is not reachable at {self.base_url}.",
            ) from exc
        finally:
            client.close()


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _chunk_from_data(data: str) -> GenerationChunk:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ProviderError("generation_failed", "The provider returned a response that was not JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("generation_failed", "The provider returned an unexpected response.")
    choices = payload.get("choices")
    text = ""
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        delta = choices[0].get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            text = delta["content"]
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    completion = usage.get("completion_tokens")
    return GenerationChunk(
        text=text,
        eval_count=completion if isinstance(completion, int) else None,
    )
