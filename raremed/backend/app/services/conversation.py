import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_CONVERSATION_TITLE
from app.core.errors import AppError
from app.models import Conversation, Message, User
from app.repositories.conversation import (
    ConversationRepository,
    empty_message_extra,
    should_replace_title,
    title_from_content,
    utcnow,
)
from app.schemas.conversation import ConversationList, ConversationRead, ConversationSummary, MessageRead
from app.services.assistant import foundation_reply


class ConversationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ConversationRepository(session)

    def list_conversations(
        self,
        owner: User,
        *,
        query: str = "",
        include_archived: bool = False,
        archived_only: bool = False,
        limit: int = 30,
        offset: int = 0,
    ) -> ConversationList:
        items, total = self.repo.list_for_owner(
            owner.id,
            query=query,
            include_archived=include_archived,
            archived_only=archived_only,
            limit=limit,
            offset=offset,
        )
        return ConversationList(
            items=[summarize(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
        )

    def create_conversation(self, owner: User, locale: str, title: str | None) -> Conversation:
        now = utcnow()
        cleaned = title.strip() if title else ""
        conversation = self.repo.add(
            owner_id=owner.id,
            locale=locale,
            title=cleaned or DEFAULT_CONVERSATION_TITLE,
            title_source="manual" if cleaned else "auto",
            now=now,
        )
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def get_conversation(self, conversation_id: uuid.UUID, owner: User) -> Conversation:
        conversation = self.repo.get_for_owner(conversation_id, owner.id, with_messages=False)
        if conversation is None:
            raise AppError("conversation_not_found", "Conversation was not found.", 404)
        return conversation

    def read_conversation(
        self,
        conversation_id: uuid.UUID,
        owner: User,
        *,
        limit: int = 50,
        before: uuid.UUID | None = None,
    ) -> ConversationRead:
        conversation = self.get_conversation(conversation_id, owner)
        messages, has_more = self.repo.older_messages(conversation, limit=limit, before_id=before)
        return ConversationRead(
            id=conversation.id,
            title=conversation.title,
            title_source=conversation.title_source,
            locale=conversation.locale,
            archived=conversation.archived_at is not None,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[MessageRead.model_validate(item) for item in messages],
            has_more=has_more,
        )

    def update_conversation(
        self,
        conversation_id: uuid.UUID,
        owner: User,
        *,
        title: str | None,
        archived: bool | None,
    ) -> Conversation:
        conversation = self.get_conversation(conversation_id, owner)
        now = utcnow()
        if title is not None:
            conversation.title = title
            conversation.title_source = "manual"
            conversation.updated_at = now
        if archived is True and conversation.archived_at is None:
            conversation.archived_at = now
            conversation.updated_at = now
        if archived is False and conversation.archived_at is not None:
            conversation.archived_at = None
            conversation.updated_at = now
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def add_exchange(self, conversation_id: uuid.UUID, owner: User, content: str, locale: str) -> tuple[Message, Message]:
        conversation = self.get_conversation(conversation_id, owner)
        now = utcnow()
        conversation.locale = locale
        if should_replace_title(conversation.title, conversation.title_source):
            conversation.title = title_from_content(content)
        user_message = self.repo.add_message(
            conversation=conversation,
            role="user",
            content=content,
            now=now,
            extra=empty_message_extra(),
        )
        assistant_message = self.repo.add_message(
            conversation=conversation,
            role="assistant",
            content=foundation_reply(locale),
            now=now + timedelta(milliseconds=1),
            extra=empty_message_extra(),
        )
        self.session.commit()
        self.session.refresh(user_message)
        self.session.refresh(assistant_message)
        return user_message, assistant_message

    def delete_conversation(self, conversation_id: uuid.UUID, owner: User) -> None:
        conversation = self.get_conversation(conversation_id, owner)
        self.repo.delete(conversation)
        self.session.commit()


def summarize(conversation: Conversation) -> ConversationSummary:
    preview = None
    if conversation.messages:
        preview = conversation.messages[-1].content[:140]
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        title_source=conversation.title_source,
        locale=conversation.locale,
        archived=conversation.archived_at is not None,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        preview=preview,
    )
