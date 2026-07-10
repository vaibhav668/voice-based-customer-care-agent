from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from uuid import UUID

from app.auth.dependencies import get_optional_current_user
from app.database.session import get_db
from app.database.models.campaign import Campaign
from app.database.models.conversation import Conversation
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaigns"],
)

@router.get("", response_model=dict)
def list_campaigns(
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    # Authorization check
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can access campaigns.")

    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    campaigns = db.scalars(stmt).all()

    data = []
    for c in campaigns:
        # Calculate stats for each campaign
        call_count_stmt = select(func.count(Conversation.id)).where(Conversation.campaign_id == c.id)
        call_count = db.scalar(call_count_stmt) or 0
        data.append({
            "id": str(c.id),
            "name": c.name,
            "type": c.type,
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat(),
            "call_count": call_count,
        })

    return success_response(
        data=data,
        message="Campaigns retrieved successfully",
    )

@router.get("/{campaign_id}/stats", response_model=dict)
def get_campaign_stats(
    campaign_id: str,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can access campaign stats.")

    try:
        cid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign ID format.")

    campaign = db.get(Campaign, cid)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # Calculate stats: resolved, unresolved, escalated calls
    total_stmt = select(func.count(Conversation.id)).where(Conversation.campaign_id == cid)
    total = db.scalar(total_stmt) or 0

    resolved_stmt = select(func.count(Conversation.id)).where(
        Conversation.campaign_id == cid,
        Conversation.resolution_status == "resolved"
    )
    resolved = db.scalar(resolved_stmt) or 0

    escalated_stmt = select(func.count(Conversation.id)).where(
        Conversation.campaign_id == cid,
        Conversation.resolution_status == "escalated"
    )
    escalated = db.scalar(escalated_stmt) or 0

    unresolved = total - resolved - escalated

    return success_response(
        data={
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "total_calls": total,
            "resolved_calls": resolved,
            "escalated_calls": escalated,
            "unresolved_calls": unresolved,
        },
        message="Campaign statistics calculated successfully",
    )
