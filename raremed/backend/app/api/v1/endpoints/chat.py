"""Streaming chat endpoint.

The route formats server-sent events. Model calls go through the inference
provider selected by configuration.
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.ai.model_config import ModelConfig, load_model_config
from app.ai.providers import build_provider
from app.ai.providers.base import InferenceProvider, ProviderError
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models import User
from app.schemas.chat import ChatRequest, ModelStatusRead
from app.services.chat import VisibleChunk, iterate_reply, persist_turn, probe_model, tokens_per_second

logger = logging.getLogger("raremed.chat")

router = APIRouter(tags=["chat"])


def get_inference_provider() -> tuple[InferenceProvider, ModelConfig]:
    settings = get_settings()
    config = load_model_config(settings)
    return build_provider(settings, config), config


@router.get("/models", response_model=ModelStatusRead)
def model_status() -> ModelStatusRead:
    provider, config = get_inference_provider()
    probed = probe_model(provider, config)
    return ModelStatusRead(
        provider=probed.name,
        model=config.model,
        base_url=probed.base_url,
        reachable=probed.reachable,
        model_ready=probed.model_ready,
        think=config.think,
        installed_models=probed.installed_models,
        detail=probed.detail,
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    provider, config = get_inference_provider()

    async def events() -> AsyncIterator[str]:
        async for item in _stream(body, request, provider, config, user):
            yield item

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream(
    body: ChatRequest,
    request: Request,
    provider: InferenceProvider,
    config: ModelConfig,
    user: User,
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[VisibleChunk | ProviderError | None] = asyncio.Queue()
    cancel = threading.Event()
    started = time.perf_counter()

    def produce() -> None:
        try:
            for chunk in iterate_reply(provider, config, body.messages, body.locale, cancel):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
                if cancel.is_set():
                    break
        except ProviderError as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop).result()
        except Exception as exc:
            logger.warning("chat generation failed", extra={"error_type": exc.__class__.__name__})
            asyncio.run_coroutine_threadsafe(
                queue.put(ProviderError("generation_failed", "The model stopped before it finished a reply.")),
                loop,
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    threading.Thread(target=produce, name="raremed-chat", daemon=True).start()
    visible: list[str] = []
    eval_count: int | None = None
    eval_duration_ns: int | None = None
    stopped = False
    failed = False
    saved = False
    stored_id = body.conversation_id
    stored_title = None
    try:
        while True:
            if await request.is_disconnected():
                stopped = True
                cancel.set()
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.15)
            except TimeoutError:
                continue
            if item is None:
                break
            if isinstance(item, ProviderError):
                failed = True
                yield _sse("error", {"code": item.code, "message": item.message})
                break
            if item.text:
                visible.append(item.text)
                yield _sse("token", {"text": item.text})
            if item.thinking:
                yield _sse("thinking", {"text": item.thinking})
            if item.eval_count is not None:
                eval_count = item.eval_count
            if item.eval_duration_ns is not None:
                eval_duration_ns = item.eval_duration_ns
    finally:
        cancel.set()
        answer = "".join(visible)
        if failed and not answer and not stopped:
            if not body.regenerate:
                result = persist_turn(
                    body.conversation_id,
                    body.locale,
                    body.messages[-1].content,
                    "",
                    False,
                    owner_id=user.id,
                    stopped=False,
                    model=config.model,
                )
                saved = result.saved
                stored_id = result.conversation_id or stored_id
                stored_title = result.title
        elif not failed or answer or stopped:
            result = persist_turn(
                body.conversation_id,
                body.locale,
                body.messages[-1].content,
                answer,
                body.regenerate,
                owner_id=user.id,
                stopped=stopped or failed,
                model=config.model,
            )
            saved = result.saved
            stored_id = result.conversation_id or stored_id
            stored_title = result.title

    if failed:
        return
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    yield _sse(
        "done",
        {
            "model": config.model,
            "provider": provider.name,
            "elapsed_ms": elapsed_ms,
            "eval_count": eval_count,
            "tokens_per_second": tokens_per_second(eval_count, eval_duration_ns, elapsed_ms),
            "stopped": stopped,
            "saved": saved,
            "think": config.think,
            "conversation_id": str(stored_id) if stored_id else None,
            "title": stored_title,
        },
    )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
