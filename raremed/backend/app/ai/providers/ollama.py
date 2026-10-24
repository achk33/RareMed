"""Ollama HTTP chat provider.

Streaming uses `POST /api/chat` with `stream: true`. The probe uses `/api/tags`
and does not generate text.
"""

import json
import logging
import threading
from collections.abc import Callable, Iterator

import httpx

from app.ai.providers.base import GenerationChunk, ProviderError, ProviderProbe

logger = logging.getLogger("raremed.ollama")

STREAM_TIMEOUT = httpx.Timeout(connect=3.0, read=90.0, write=30.0, pool=5.0)


def request_think(model: str, think: bool) -> bool:
    """Send Ollama's think flag only when thinking mode is on.

    Forcing think=true for Qwen3 on current Ollama builds can OOM or crash the
    runner. When thinking is off, tagged <think> blocks are stripped in chat.
    """
    return bool(think)


def model_installed(installed: list[str], expected: str) -> bool:
    wanted = expected.strip()
    if not wanted:
        return False
    for name in installed:
        if name == wanted or name.split(":")[0] == wanted or name.startswith(f"{wanted}:"):
            return True
        if wanted.endswith(":latest") and name == wanted[: -len(":latest")]:
            return True
    return False


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        *,
        probe_timeout: float = 2.0,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.probe_timeout = probe_timeout
        self._client_factory = client_factory

    def _open(self, *, probe: bool) -> httpx.Client:
        if self._client_factory is not None:
            return self._client_factory()
        timeout = self.probe_timeout if probe else STREAM_TIMEOUT
        return httpx.Client(timeout=timeout)

    def probe(self, model: str) -> ProviderProbe:
        client = self._open(probe=True)
        try:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("ollama probe failed", extra={"error_type": exc.__class__.__name__})
            return ProviderProbe(
                name=self.name,
                model=model,
                base_url=self.base_url,
                reachable=False,
                model_ready=False,
                detail=exc.__class__.__name__,
            )
        finally:
            client.close()

        installed: list[str] = []
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    installed.append(item["name"])
                if len(installed) == 20:
                    break
        return ProviderProbe(
            name=self.name,
            model=model,
            base_url=self.base_url,
            reachable=True,
            model_ready=model_installed(installed, model),
            installed_models=installed,
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
        if cancel.is_set():
            return
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        if request_think(model, think):
            payload["think"] = True
        client = self._open(probe=False)
        try:
            with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", errors="replace")[:500]
                    raise _http_error(model, response.status_code, body)
                for line in response.iter_lines():
                    if cancel.is_set():
                        return
                    if not line:
                        continue
                    yield _chunk_from_line(line, model)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "generation_failed",
                "The model stopped responding before the reply finished.",
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("ollama stream failed", extra={"error_type": exc.__class__.__name__})
            raise ProviderError(
                "ollama_unavailable",
                f"Ollama is not reachable at {self.base_url}. Start Ollama, then run: ollama pull {model}",
            ) from exc
        finally:
            client.close()


def _http_error(model: str, status_code: int, body: str) -> ProviderError:
    lowered = body.lower()
    logger.warning("ollama chat rejected", extra={"status_code": status_code, "body": body[:300]})
    if status_code == 404 or "not found" in lowered:
        return ProviderError(
            "model_missing",
            f"The model {model} is not installed in Ollama. Run: ollama pull {model}",
        )
    if "out of memory" in lowered or "outofmemory" in lowered:
        return ProviderError(
            "generation_failed",
            "The model ran out of GPU memory. Close other GPU apps, then try again.",
        )
    if "terminated" in lowered or "overrun" in lowered:
        return ProviderError(
            "generation_failed",
            "Ollama crashed while starting the model. Try the reply again.",
        )
    return ProviderError(
        "generation_failed",
        "Ollama rejected the chat request.",
    )


def _chunk_from_line(line: str, model: str) -> GenerationChunk:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProviderError("generation_failed", "Ollama returned a response that was not JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("generation_failed", "Ollama returned an unexpected response.")
    error = payload.get("error")
    if isinstance(error, str) and error:
        if "not found" in error.lower():
            raise ProviderError(
                "model_missing",
                f"The model {model} is not installed in Ollama. Run: ollama pull {model}",
            )
        raise ProviderError("generation_failed", "Ollama could not generate a reply.")
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    text = message.get("content") if isinstance(message.get("content"), str) else ""
    thinking = message.get("thinking") if isinstance(message.get("thinking"), str) else ""
    eval_count = payload.get("eval_count")
    eval_duration = payload.get("eval_duration")
    return GenerationChunk(
        text=text,
        thinking=thinking,
        done=bool(payload.get("done")),
        eval_count=eval_count if isinstance(eval_count, int) else None,
        eval_duration_ns=eval_duration if isinstance(eval_duration, int) else None,
    )
