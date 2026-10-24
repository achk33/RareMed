"""Inference provider contract.

Chat orchestration depends on this interface. Ollama, OpenAI-compatible APIs,
and vLLM each implement it.
"""

import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class GenerationChunk:
    text: str = ""
    thinking: str = ""
    done: bool = False
    eval_count: int | None = None
    eval_duration_ns: int | None = None


@dataclass
class ProviderProbe:
    name: str
    model: str
    base_url: str
    reachable: bool
    model_ready: bool
    installed_models: list[str] = field(default_factory=list)
    detail: str | None = None


class InferenceProvider(Protocol):
    name: str

    def probe(self, model: str) -> ProviderProbe: ...

    def stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        num_ctx: int,
        think: bool,
        cancel: threading.Event,
    ) -> Iterator[GenerationChunk]: ...
