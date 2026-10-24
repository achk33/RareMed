"""Stream a language-model reply and optionally store the turn.

The chat controller calls this service. Provider selection stays in the
inference registry.
"""

import logging
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from app.ai.model_config import ModelConfig
from app.ai.prompts import system_prompt
from app.ai.providers.base import InferenceProvider, ProviderProbe
from app.ai.thinking import ThinkSplitter
from app.core.constants import DEFAULT_CONVERSATION_TITLE
from app.core.database import get_session_factory
from app.repositories.conversation import (
    ConversationRepository,
    empty_message_extra,
    should_replace_title,
    title_from_content,
    utcnow,
)
from app.schemas.chat import ChatMessageIn

logger = logging.getLogger("raremed.chat")


@dataclass
class VisibleChunk:
    text: str = ""
    thinking: str = ""
    done: bool = False
    eval_count: int | None = None
    eval_duration_ns: int | None = None


def trim_messages(messages: list[dict[str, str]], num_ctx: int) -> list[dict[str, str]]:
    """Keep the system prompt and the newest turns inside a character budget."""
    if not messages:
        return messages
    budget = max(512, int(num_ctx * 0.75)) * 4
    system = messages[0]
    rest = messages[1:]
    kept: list[dict[str, str]] = []
    used = len(system.get("content", ""))
    for message in reversed(rest):
        cost = len(message.get("content", "")) + 8
        if kept and used + cost > budget:
            break
        kept.append(message)
        used += cost
    kept.reverse()
    if not kept and rest:
        kept = [rest[-1]]
    return [system, *kept]


def iterate_reply(
    provider: InferenceProvider,
    config: ModelConfig,
    history: list[ChatMessageIn],
    locale: str,
    cancel: threading.Event,
) -> Iterator[VisibleChunk]:
    prompt = [
        {"role": "system", "content": system_prompt(locale)},
        *[{"role": item.role, "content": item.content} for item in history],
    ]
    splitter = ThinkSplitter()
    for chunk in provider.stream(
        messages=trim_messages(prompt, config.num_ctx),
        model=config.model,
        temperature=config.temperature,
        num_ctx=config.num_ctx,
        think=config.think,
        cancel=cancel,
    ):
        visible, tagged = splitter.feed(chunk.text)
        thinking = f"{chunk.thinking}{tagged}" if config.think else ""
        if chunk.done:
            tail_visible, tail_thinking = splitter.flush()
            visible = f"{visible}{tail_visible}"
            if config.think:
                thinking = f"{thinking}{tail_thinking}"
        if visible or thinking or chunk.done:
            yield VisibleChunk(
                text=visible,
                thinking=thinking,
                done=chunk.done,
                eval_count=chunk.eval_count,
                eval_duration_ns=chunk.eval_duration_ns,
            )


def tokens_per_second(
    eval_count: int | None,
    eval_duration_ns: int | None,
    elapsed_ms: int,
) -> float | None:
    if not eval_count:
        return None
    if eval_duration_ns and eval_duration_ns > 0:
        return round(eval_count / (eval_duration_ns / 1_000_000_000), 1)
    if elapsed_ms > 0:
        return round(eval_count / (elapsed_ms / 1000), 1)
    return None


@dataclass
class PersistResult:
    saved: bool
    conversation_id: uuid.UUID | None = None
    title: str | None = None


def save_turn(
    conversation_id: uuid.UUID | None,
    locale: str,
    user_content: str,
    assistant_content: str,
    regenerate: bool,
    *,
    owner_id: uuid.UUID | None = None,
    stopped: bool = False,
    model: str | None = None,
) -> bool:
    return persist_turn(
        conversation_id,
        locale,
        user_content,
        assistant_content,
        regenerate,
        owner_id=owner_id,
        stopped=stopped,
        model=model,
    ).saved


def persist_turn(
    conversation_id: uuid.UUID | None,
    locale: str,
    user_content: str,
    assistant_content: str,
    regenerate: bool,
    *,
    owner_id: uuid.UUID | None = None,
    stopped: bool = False,
    model: str | None = None,
) -> PersistResult:
    """Store the turn when PostgreSQL is up. Failure does not discard the reply."""
    try:
        session = get_session_factory()()
    except Exception as exc:
        logger.warning("chat persistence unavailable", extra={"error_type": exc.__class__.__name__})
        return PersistResult(False)
    try:
        repo = ConversationRepository(session)
        conversation = repo.get(conversation_id) if conversation_id is not None else None
        if conversation is not None and owner_id is not None and conversation.owner_id != owner_id:
            return PersistResult(False)
        if conversation is None:
            if owner_id is None or regenerate:
                return PersistResult(False)
            now = utcnow()
            conversation = repo.add(
                owner_id=owner_id,
                locale=locale,
                title=title_from_content(user_content) or DEFAULT_CONVERSATION_TITLE,
                title_source="auto",
                now=now,
            )
        now = utcnow()
        conversation.locale = locale
        extra = empty_message_extra()
        if model:
            extra["model"] = model
        extra["stopped"] = stopped
        status = "interrupted" if stopped else "complete"
        if regenerate:
            last = conversation.messages[-1] if conversation.messages else None
            if last is not None and last.role == "assistant":
                last.content = assistant_content
                last.status = status if assistant_content or stopped else last.status
                last.extra = extra
                conversation.updated_at = now
            elif assistant_content or stopped:
                repo.add_message(
                    conversation=conversation,
                    role="assistant",
                    content=assistant_content,
                    now=now,
                    status=status,
                    extra=extra,
                )
        else:
            if should_replace_title(conversation.title, conversation.title_source):
                conversation.title = title_from_content(user_content)
            repo.add_message(
                conversation=conversation,
                role="user",
                content=user_content,
                now=now,
                extra=empty_message_extra(),
            )
            if assistant_content or stopped:
                repo.add_message(
                    conversation=conversation,
                    role="assistant",
                    content=assistant_content,
                    now=now + timedelta(milliseconds=1),
                    status=status,
                    extra=extra,
                )
        session.commit()
        return PersistResult(True, conversation.id, conversation.title)
    except Exception as exc:
        session.rollback()
        logger.warning("chat persistence failed", extra={"error_type": exc.__class__.__name__})
        return PersistResult(False)
    finally:
        session.close()


def probe_model(provider: InferenceProvider, config: ModelConfig) -> ProviderProbe:
    started = time.perf_counter()
    result = provider.probe(config.model)
    logger.debug("model probe %.1fms", (time.perf_counter() - started) * 1000)
    return result


