import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import LocaleCode


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    locale: LocaleCode = "en"

    @field_validator("content")
    @classmethod
    def content_must_contain_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message content is empty.")
        return stripped


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str = "complete"
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    locale: LocaleCode = "en"
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Title is empty.")
        return cleaned


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    title_source: str = "auto"
    locale: str
    archived: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: int
    preview: str | None = None


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str
    title_source: str = "auto"
    locale: str
    archived: bool = False
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead]
    has_more: bool = False


class MessageExchange(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead


TitleSource = Literal["auto", "manual"]
