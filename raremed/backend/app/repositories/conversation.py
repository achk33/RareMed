import uuid
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import DEFAULT_CONVERSATION_TITLE
from app.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        query: str = "",
        include_archived: bool = False,
        archived_only: bool = False,
        limit: int = 30,
        offset: int = 0,
    ) -> tuple[list[Conversation], int]:
        filters = [Conversation.owner_id == owner_id]
        if archived_only:
            filters.append(Conversation.archived_at.is_not(None))
        elif not include_archived:
            filters.append(Conversation.archived_at.is_(None))
        needle = query.strip()
        if needle:
            pattern = f"%{_like_escape(needle)}%"
            message_match = (
                select(Message.conversation_id)
                .where(Message.conversation_id == Conversation.id)
                .where(Message.content.ilike(pattern, escape="\\"))
                .exists()
            )
            filters.append(
                or_(
                    Conversation.title.ilike(pattern, escape="\\"),
                    message_match,
                )
            )
        count = self.session.scalar(
            select(func.count()).select_from(Conversation).where(*filters)
        )
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(*filters)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement).all()), int(count or 0)

    def list_recent(self, limit: int = 100) -> list[Conversation]:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def get(self, conversation_id: uuid.UUID, *, with_messages: bool = True) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id)
        if with_messages:
            statement = statement.options(selectinload(Conversation.messages))
        return self.session.scalar(statement)

    def get_for_owner(
        self,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        with_messages: bool = True,
    ) -> Conversation | None:
        conversation = self.get(conversation_id, with_messages=with_messages)
        if conversation is None or conversation.owner_id != owner_id:
            return None
        return conversation

    def add(
        self,
        *,
        owner_id: uuid.UUID,
        locale: str,
        title: str,
        now: datetime,
        title_source: str = "auto",
    ) -> Conversation:
        conversation = Conversation(
            owner_id=owner_id,
            title=title,
            title_source=title_source,
            locale=locale,
            created_at=now,
            updated_at=now,
        )
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def add_message(
        self,
        *,
        conversation: Conversation,
        role: str,
        content: str,
        now: datetime,
        status: str = "complete",
        extra: dict | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            status=status,
            extra=extra if extra is not None else empty_message_extra(),
            created_at=now,
        )
        self.session.add(message)
        conversation.updated_at = now
        self.session.flush()
        return message

    def older_messages(
        self,
        conversation: Conversation,
        *,
        limit: int,
        before_id: uuid.UUID | None,
    ) -> tuple[list[Message], bool]:
        filters = [Message.conversation_id == conversation.id]
        if before_id is not None:
            pivot = self.session.get(Message, before_id)
            if pivot is None or pivot.conversation_id != conversation.id:
                return [], False
            filters.append(
                or_(
                    Message.created_at < pivot.created_at,
                    (Message.created_at == pivot.created_at) & (cast(Message.id, String) < str(pivot.id)),
                )
            )
        statement = (
            select(Message)
            .where(*filters)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
        rows = list(self.session.scalars(statement).all())
        has_more = len(rows) > limit
        page = list(reversed(rows[:limit]))
        return page, has_more

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def title_from_content(content: str) -> str:
    compact = " ".join(content.split())
    if not compact:
        return DEFAULT_CONVERSATION_TITLE
    if len(compact) <= 72:
        return compact
    return compact[:71].rstrip() + "…"


def should_replace_title(title: str, title_source: str = "auto") -> bool:
    if title_source == "manual":
        return False
    return title.strip() == "" or title == DEFAULT_CONVERSATION_TITLE


def empty_message_extra() -> dict:
    return {
        "medical_evidence": [],
        "hpo_entities": [],
        "diagnostic_session_id": None,
    }


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
