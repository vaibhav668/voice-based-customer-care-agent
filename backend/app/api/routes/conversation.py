from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_optional_current_user
from app.database.session import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import (
    ConversationDetailSchema,
    ConversationSchema,
    PaginatedConversationsResponse,
)
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["Conversations"],
)


@router.get("", response_model=dict)
def list_conversations(
    channel: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    role = current_user.get("role") if current_user else None
    is_admin = (role == "ADMIN")

    # Load conversations for this authenticated user and guest sessions
    total, conversations = repo.list_conversations(
        user_id=user_id,
        channel=channel,
        status=status,
        limit=limit,
        offset=offset,
        is_admin=is_admin,
    )

    data = [ConversationSchema.model_validate(c).model_dump(mode="json") for c in conversations]

    return success_response(
        data={
            "total": total,
            "limit": limit,
            "offset": offset,
            "conversations": data,
        },
        message="Conversations retrieved successfully",
    )


@router.get("/search", response_model=dict)
def search_conversations(
    q: str | None = Query(None, alias="q"),
    booking_code: str | None = Query(None),
    intent: str | None = Query(None),
    language: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    role = current_user.get("role") if current_user else None
    is_admin = (role == "ADMIN")

    # Search across conversations (matching this user's or guest sessions)
    total, conversations = repo.search_conversations(
        search_query=q,
        booking_code=booking_code,
        intent=intent,
        language=language,
        user_id=user_id,
        limit=limit,
        offset=offset,
        is_admin=is_admin,
    )

    data = [ConversationSchema.model_validate(c).model_dump(mode="json") for c in conversations]

    return success_response(
        data={
            "total": total,
            "limit": limit,
            "offset": offset,
            "conversations": data,
        },
        message="Search completed successfully",
    )


@router.get("/{conversation_id}", response_model=dict)
def get_conversation_detail(
    conversation_id: str,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = repo.get_by_id(conversation_id)

    if not conv:
        return success_response(
            data=None,
            message="Conversation not found",
        )

    # Security check: If conversation belongs to another user, restrict access
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    role = current_user.get("role") if current_user else None
    if role != "ADMIN" and conv.user_id and str(conv.user_id) != str(user_id):
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access to this conversation is unauthorized")

    data = ConversationDetailSchema.model_validate(conv).model_dump(mode="json")

    return success_response(
        data=data,
        message="Conversation details fetched successfully",
    )


@router.delete("/{conversation_id}", response_model=dict)
def delete_conversation(
    conversation_id: str,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = repo.get_by_id(conversation_id)

    if not conv:
        return success_response(
            data={"deleted": False},
            message="Conversation not found",
        )

    # Security check: If conversation belongs to another user, restrict access
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    role = current_user.get("role") if current_user else None
    if role != "ADMIN" and conv.user_id and str(conv.user_id) != str(user_id):
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access to this conversation is unauthorized")

    deleted = repo.soft_delete(conversation_id)

    return success_response(
        data={"deleted": deleted},
        message="Conversation deleted successfully" if deleted else "Conversation not found",
    )
