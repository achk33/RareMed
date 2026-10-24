import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationList,
    ConversationRead,
    ConversationSummary,
    ConversationUpdate,
    MessageCreate,
    MessageExchange,
    MessageRead,
)
from app.services.conversation import ConversationService, summarize

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationList)
def list_conversations(
    q: str = "",
    include_archived: bool = False,
    archived_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationList:
    return ConversationService(session).list_conversations(
        user,
        query=q,
        include_archived=include_archived,
        archived_only=archived_only,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ConversationRead, status_code=201)
def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationRead:
    conversation = ConversationService(session).create_conversation(user, body.locale, body.title)
    return ConversationRead(
        id=conversation.id,
        title=conversation.title,
        title_source=conversation.title_source,
        locale=conversation.locale,
        archived=False,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[],
        has_more=False,
    )


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    before: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationRead:
    return ConversationService(session).read_conversation(
        conversation_id,
        user,
        limit=limit,
        before=before,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationSummary:
    conversation = ConversationService(session).update_conversation(
        conversation_id,
        user,
        title=body.title,
        archived=body.archived,
    )
    return summarize(conversation)


@router.post("/{conversation_id}/messages", response_model=MessageExchange, status_code=201)
def add_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> MessageExchange:
    user_message, assistant_message = ConversationService(session).add_exchange(
        conversation_id,
        user,
        body.content,
        body.locale,
    )
    return MessageExchange(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    ConversationService(session).delete_conversation(conversation_id, user)
    return Response(status_code=204)
