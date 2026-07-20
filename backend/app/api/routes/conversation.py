from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.auth.dependencies import get_optional_current_user
from app.database.session import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import (
    ConversationDetailSchema,
    ConversationSchema,
    PaginatedConversationsResponse,
    ConversationMessageSchema,
)
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["Conversations"],
)


@router.get("/admin/enriched", response_model=dict)
def list_admin_enriched_conversations(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint: returns all conversations enriched with user phone, name, and booking details."""
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access restricted to administrators")

    from app.database.models.conversation import Conversation
    from app.database.models.user import User
    from app.database.models.booking import Booking
    from app.database.models.trip import Trip
    from app.database.models.route import Route
    from app.database.models.conversation_message import ConversationMessage
    import json

    stmt = (
        select(Conversation)
        .where(Conversation.is_deleted == False)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = db.scalars(stmt).all()

    enriched = []
    for conv in conversations:
        user_phone = None
        user_name = None
        booking_code = None
        booking_details = None

        # Fetch messages first to use for entity/text parsing
        msgs = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at)
            .all()
        )

        # 1. Look up registered user info directly linked to conversation
        if conv.user:
            user_phone = conv.user.phone
            user_name = conv.user.full_name

        # Try to get booking code from messages
        msg_with_booking = None
        for m in msgs:
            if m.booking_code:
                booking_code = m.booking_code
                break

        # Alternatively try from conv.booking
        if not booking_code and conv.booking:
            booking_code = conv.booking.booking_code

        # Fetch booking details if code found
        if booking_code:
            bk = conv.booking if (conv.booking and conv.booking.booking_code == booking_code) else db.query(Booking).filter_by(booking_code=booking_code).first()
            if bk:
                trip = bk.trip
                route = trip.route if trip else None
                booking_details = {
                    "booking_code": booking_code,
                    "seat_number": bk.seat_number,
                    "booking_status": bk.booking_status.value if hasattr(bk.booking_status, "value") else str(bk.booking_status),
                    "payment_status": bk.payment_status.value if hasattr(bk.payment_status, "value") else str(bk.payment_status),
                    "departure_time": trip.departure_time.isoformat() if (trip and trip.departure_time) else None,
                    "arrival_time": trip.arrival_time.isoformat() if (trip and trip.arrival_time) else None,
                    "source": route.source_city if route else None,
                    "destination": route.destination_city if route else None,
                }
                # 2. Fallback to booking owner if conversation itself is guest
                if not user_phone and bk.user:
                    user_phone = bk.user.phone
                    user_name = bk.user.full_name

        # 3. Check if session_id is a phone number (e.g. voice call)
        if not user_phone and conv.session_id and conv.session_id.isdigit() and len(conv.session_id) >= 10:
            user_phone = conv.session_id

        # 4. Search messages for phone number entities or text matches
        if not user_phone:
            import re
            for m in msgs:
                ent = m.entities
                if isinstance(ent, str):
                    try:
                        ent = json.loads(ent)
                    except:
                        ent = {}
                if isinstance(ent, dict) and ent.get("phone_number"):
                    user_phone = ent.get("phone_number")
                    break
                # Regex match for a standard 10-digit number
                match = re.search(r'\b[6-9]\d{9}\b', m.message)
                if match:
                    user_phone = match.group(0)
                    break

        # Dynamic linking: link conversation to user ID if we found a registered phone
        if user_phone and not conv.user_id:
            clean_phone = "".join(filter(str.isdigit, str(user_phone)))
            if len(clean_phone) > 10:
                clean_phone = clean_phone[-10:]
            user = db.query(User).filter(User.phone == clean_phone).first()
            if user:
                conv.user_id = user.id
                db.commit()
                user_name = user.full_name
                user_phone = user.phone

        # If phone still not resolved, show as Unknown but still include in CRM
        if not user_phone:
            user_phone = "Unknown"
        if not user_name:
            user_name = "Guest"

        user_messages = [m.message for m in msgs if m.sender == "USER"]
        ai_messages = [m.message for m in msgs if m.sender == "AI"]
        intents = list({m.intent for m in msgs if m.intent})
        tools = list({m.tool_used for m in msgs if m.tool_used})

        # Infer possible problem from last user message and resolution status
        last_user_msg = user_messages[-1] if user_messages else None
        possible_problem = last_user_msg if last_user_msg else "No user input recorded"
        if conv.resolution_status == "escalated":
            possible_problem = f"⚠️ Escalated — {possible_problem}"
        elif conv.resolution_status == "unresolved":
            possible_problem = f"🔴 Unresolved — {possible_problem}"

        # Query matching IvrSession
        from app.database.models.ivr_session import IvrSession
        from app.database.models.customer_feedback import CustomerFeedback
        from datetime import datetime

        ivr_state = "UNKNOWN"
        ivr_sess = db.query(IvrSession).filter_by(session_id=conv.session_id).first()
        if ivr_sess:
            ivr_state = ivr_sess.state
            if ivr_sess.booking_code and not booking_code:
                booking_code = ivr_sess.booking_code
            if ivr_sess.phone_number and user_phone == "Unknown":
                user_phone = ivr_sess.phone_number

        # Fetch feedback rating
        fb = db.query(CustomerFeedback).filter_by(conversation_id=conv.id).first()
        rating = fb.rating if fb else None

        # Compute duration
        duration = 0
        if conv.started_at:
            try:
                end_time = conv.ended_at or datetime.now()
                if conv.started_at.tzinfo is not None and end_time.tzinfo is None:
                    from datetime import timezone
                    end_time = end_time.replace(tzinfo=timezone.utc)
                elif conv.started_at.tzinfo is None and end_time.tzinfo is not None:
                    end_time = end_time.replace(tzinfo=None)
                duration = int((end_time - conv.started_at).total_seconds())
            except Exception:
                duration = 0

        enriched.append({
            "id": str(conv.id),
            "session_id": conv.session_id,
            "user_id": str(conv.user_id) if conv.user_id else None,
            "user_phone": user_phone,
            "user_name": user_name,
            "channel": conv.channel.value if hasattr(conv.channel, "value") else str(conv.channel),
            "language": conv.language,
            "status": conv.status.value if hasattr(conv.status, "value") else str(conv.status),
            "resolution_status": conv.resolution_status or "unresolved",
            "current_intent": conv.current_intent,
            "message_count": conv.message_count or 0,
            "sentiment": conv.sentiment,
            "summary": conv.summary,
            "booking_code": booking_code,
            "booking_details": booking_details,
            "intents_detected": intents,
            "tools_used": tools,
            "possible_problem": possible_problem,
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "ivr_state": ivr_state,
            "rating": rating,
            "duration": duration,
        })

    avg_ai_latency_sec = 0.0
    try:
        from app.database.models.conversation_message import ConversationMessage
        avg_ms = db.scalar(select(func.avg(ConversationMessage.response_time_ms)).where(ConversationMessage.sender == "AI"))
        if avg_ms:
            avg_ai_latency_sec = round(avg_ms / 1000, 2)
    except Exception as e:
        print(f"Error computing average response time: {e}")

    return success_response(
        data={"conversations": enriched, "total": len(enriched), "avg_ai_latency_sec": avg_ai_latency_sec},
        message="Admin enriched conversations fetched",
    )


@router.get("/admin/reviews", response_model=dict)
def get_admin_reviews(
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint: returns all customer reviews/feedbacks with conversation details."""
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access restricted to administrators")

    from app.database.models.customer_feedback import CustomerFeedback
    from app.database.models.conversation import Conversation
    from app.database.models.user import User

    stmt = select(CustomerFeedback).order_by(CustomerFeedback.created_at.desc())
    feedbacks = db.scalars(stmt).all()

    reviews = []
    for fb in feedbacks:
        conv = fb.conversation
        user_name = fb.user.full_name if fb.user else "Guest"
        user_phone = fb.user.phone if fb.user else (conv.session_id if (conv and conv.session_id.isdigit()) else "Unknown")
        reviews.append({
            "id": str(fb.id),
            "conversation_id": str(fb.conversation_id),
            "rating": fb.rating,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
            "user_name": user_name,
            "user_phone": user_phone,
            "resolution_status": conv.resolution_status if conv else "resolved",
        })

    return success_response(
        data={"reviews": reviews, "total": len(reviews)},
        message="Admin customer reviews fetched",
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
    
    # Query matching IvrSession
    from app.database.models.ivr_session import IvrSession
    from app.database.models.customer_feedback import CustomerFeedback
    from datetime import datetime

    ivr_state = "UNKNOWN"
    ivr_sess = db.query(IvrSession).filter_by(session_id=conv.session_id).first()
    if ivr_sess:
        ivr_state = ivr_sess.state

    # Fetch feedback rating
    fb = db.query(CustomerFeedback).filter_by(conversation_id=conv.id).first()
    rating = fb.rating if fb else None

    # Compute duration
    duration = 0
    if conv.started_at:
        try:
            end_time = conv.ended_at or datetime.now()
            if conv.started_at.tzinfo is not None and end_time.tzinfo is None:
                from datetime import timezone
                end_time = end_time.replace(tzinfo=timezone.utc)
            elif conv.started_at.tzinfo is None and end_time.tzinfo is not None:
                end_time = end_time.replace(tzinfo=None)
            duration = int((end_time - conv.started_at).total_seconds())
        except Exception:
            duration = 0

    data["ivr_state"] = ivr_state
    data["rating"] = rating
    data["duration"] = duration
    
    # If requester is an admin and conversation is associated with a registered user, fetch all messages from all user conversations
    if role == "ADMIN" and conv.user_id:
        from app.database.models.conversation import Conversation
        from app.database.models.conversation_message import ConversationMessage

        # Get all conversations for this user
        user_conv_ids = db.scalars(
            select(Conversation.id).where(Conversation.user_id == conv.user_id, Conversation.is_deleted == False)
        ).all()

        # Query all messages for these conversations
        all_msgs = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id.in_(user_conv_ids))
            .order_by(ConversationMessage.created_at.asc())
        ).all()

        data["messages"] = [
            ConversationMessageSchema.model_validate(m).model_dump(mode="json")
            for m in all_msgs
        ]

    # Gate recording_url by admin role
    if role != "ADMIN":
        data["recording_url"] = None

    return success_response(
        data=data,
        message="Conversation details fetched successfully",
    )


@router.get("/analytics/bookings", response_model=dict)
def list_analytics_bookings(
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    # Only allow admin access
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access restricted to administrators")

    from app.database.models.booking import Booking
    from app.database.models.trip import Trip
    from app.database.models.route import Route
    from sqlalchemy.orm import joinedload

    stmt = (
        select(Booking)
        .options(
            joinedload(Booking.trip).joinedload(Trip.route)
        )
        .order_by(Booking.created_at.desc())
    )
    bookings = db.scalars(stmt).all()

    res_bookings = []
    for bk in bookings:
        trip = bk.trip
        route = trip.route if trip else None
        res_bookings.append({
            "booking_code": bk.booking_code,
            "source": route.source_city if route else "N/A",
            "destination": route.destination_city if route else "N/A",
            "seat_number": bk.seat_number,
            "departure_time": trip.departure_time.strftime("%Y-%m-%d %I:%M %p") if (trip and trip.departure_time) else "N/A",
            "arrival_time": trip.arrival_time.strftime("%Y-%m-%d %I:%M %p") if (trip and trip.arrival_time) else "N/A",
            "payment_status": bk.payment_status.value if hasattr(bk.payment_status, "value") else str(bk.payment_status),
            "booking_status": bk.booking_status.value if hasattr(bk.booking_status, "value") else str(bk.booking_status),
        })

    return success_response(
        data=res_bookings,
        message="Analytics bookings fetched successfully",
    )


@router.put("/{conversation_id}/resolution", response_model=dict)
def update_resolution_status(
    conversation_id: str,
    status: str = Query(..., description="resolved, unresolved, escalated"),
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    # Only allow admin access
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        from app.exceptions.common import UnauthorizedException
        raise UnauthorizedException("Access restricted to administrators")

    repo = ConversationRepository(db)
    conv = repo.get_by_id(conversation_id)
    if not conv:
        from app.exceptions.common import NotFoundException
        raise NotFoundException("Conversation not found")

    conv.resolution_status = status.lower()
    db.commit()
    db.refresh(conv)

    return success_response(
        data={"id": str(conv.id), "resolution_status": conv.resolution_status},
        message="Resolution status updated successfully",
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
