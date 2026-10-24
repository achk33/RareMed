import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import LocaleCode


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def content_must_contain_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message content is empty.")
        return stripped


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=32)
    locale: LocaleCode = "en"
    conversation_id: uuid.UUID | None = None
    regenerate: bool = False

    @field_validator("messages")
    @classmethod
    def last_message_is_from_the_user(cls, value: list[ChatMessageIn]) -> list[ChatMessageIn]:
        if value[-1].role != "user":
            raise ValueError("The last message must be from the user.")
        return value


class ModelStatusRead(BaseModel):
    provider: str
    model: str
    base_url: str
    reachable: bool
    model_ready: bool
    think: bool
    installed_models: list[str]
    detail: str | None = None
