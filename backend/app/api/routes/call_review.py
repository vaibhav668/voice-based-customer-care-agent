from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel

from app.auth.dependencies import get_optional_current_user
from app.database.session import get_db
from app.database.models.call_review import CallReview
from app.database.models.conversation import Conversation
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["Call Reviews"],
)

class CreateReviewSchema(BaseModel):
    outcome_tag: str
    notes: str | None = None

@router.post("/{conversation_id}/reviews", response_model=dict)
def create_call_review(
    conversation_id: str,
    payload: CreateReviewSchema,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    # Authorization check: only admin users
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can review calls.")

    admin_id = current_user.get("sub") or current_user.get("id")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Authentication credentials required.")

    try:
        conv_id = UUID(conversation_id)
        admin_uid = UUID(str(admin_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    review = CallReview(
        call_id=conv_id,
        admin_id=admin_uid,
        outcome_tag=payload.outcome_tag,
        notes=payload.notes,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return success_response(
        data={
            "id": str(review.id),
            "call_id": str(review.call_id),
            "admin_id": str(review.admin_id),
            "outcome_tag": review.outcome_tag,
            "notes": review.notes,
            "reviewed_at": review.reviewed_at.isoformat(),
        },
        message="Call review created successfully",
    )

@router.get("/{conversation_id}/reviews", response_model=dict)
def list_call_reviews(
    conversation_id: str,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    # Authorization check: only admin users
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can access call reviews.")

    try:
        conv_id = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    stmt = select(CallReview).where(CallReview.call_id == conv_id).order_by(CallReview.reviewed_at.desc())
    reviews = db.scalars(stmt).all()

    data = [{
        "id": str(r.id),
        "call_id": str(r.call_id),
        "admin_id": str(r.admin_id),
        "outcome_tag": r.outcome_tag,
        "notes": r.notes,
        "reviewed_at": r.reviewed_at.isoformat(),
    } for r in reviews]

    return success_response(
        data=data,
        message="Call reviews retrieved successfully",
    )
