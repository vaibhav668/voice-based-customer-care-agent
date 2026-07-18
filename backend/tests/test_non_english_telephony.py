import os
import sys
import uuid
import pytest
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from main import app
from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.database.models.user import User, UserRole
from app.database.models.booking import Booking, BookingStatus, PaymentStatus
from app.database.models.trip import Trip, TripStatus
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.ivr_session import IvrSession
from app.database.models.conversation import Conversation
from app.database.models.conversation_message import ConversationMessage
from app.database.models.customer_feedback import CustomerFeedback
from app.voice.ivr import ivr_manager, IVRState


@pytest.mark.asyncio
async def test_non_english_hindi_telephony_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    phone_number = "9876543211"
    email = "hindi_telephony_tester@example.com"
    booking_code = "BK-HINDI"

    # Clean existing
    user = db.query(User).filter_by(email=email).first()
    if user:
        db.delete(user)
        db.commit()

    user = User(
        id=uuid.uuid4(),
        full_name="Hindi Telephony Tester",
        email=email,
        phone=phone_number,
        password_hash="pass",
        role=UserRole.CUSTOMER,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()

    route = Route(source_city="Delhi", destination_city="Goa", distance_km=600, estimated_duration_minutes=540)
    db.add(route)
    db.commit()

    bus = Bus(bus_number="BUSHIN", bus_name="Hindi Express", registration_number="HIND123", capacity=36, bus_type=BusType.AC_SLEEPER)
    db.add(bus)
    db.commit()

    departure_time = datetime.now() + timedelta(days=2)
    trip = Trip(
        route_id=route.id,
        bus_id=bus.id,
        departure_time=departure_time,
        arrival_time=departure_time + timedelta(hours=9),
        status=TripStatus.SCHEDULED,
        available_seats=30
    )
    db.add(trip)
    db.commit()

    booking = Booking(
        booking_code=booking_code,
        user_id=user.id,
        trip_id=trip.id,
        seat_number="H1",
        booking_status=BookingStatus.CONFIRMED,
        payment_status=PaymentStatus.PAID
    )
    db.add(booking)
    db.commit()

    call_uuid = f"CA-HindiTest-{uuid.uuid4().hex[:6]}"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # 1. Incoming Call
        res = await client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": phone_number})
        assert res.status_code == 200
        assert "language" in res.text

        # 2. Select Hindi (Digits=2)
        res = await client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "2"})
        assert res.status_code == 200
        session = ivr_manager.calls[call_uuid]
        assert session.language == "hi"
        assert "verify_code" in res.text

        # 3. Enter Booking Code (BK-HINDI)
        res = await client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
        assert res.status_code == 200
        assert session.state == IVRState.ACTIVE_AGENT
        assert session.language == "hi"
        # Must have Record tag or Speak in hi-IN
        assert "agent" in res.text
        assert "hi-IN" in res.text or "Polly.Aditi" in res.text

        # 4. Agent turn with SpeechResult (e.g. ASR transcript fallback or text turn)
        res = await client.post("/api/v1/telephony/plivo/agent", data={"CallUUID": call_uuid, "SpeechResult": "मेरी बस का क्या स्टेटस है?"})
        assert res.status_code == 200
        assert "query_choice" in res.text
        assert "hi-IN" in res.text or "Polly.Aditi" in res.text

        # 5. Query Choice with Digits=1 (asks for second query in Hindi)
        res = await client.post("/api/v1/telephony/plivo/query_choice", data={"CallUUID": call_uuid, "Digits": "1"})
        assert res.status_code == 200
        assert "agent" in res.text
        assert "hi-IN" in res.text or "Polly.Aditi" in res.text

        # 6. Query Choice with SpeechResult (direct speech during choice phase)
        res = await client.post("/api/v1/telephony/plivo/query_choice", data={"CallUUID": call_uuid, "SpeechResult": "बस कब पहुंचेगी?"})
        assert res.status_code == 200
        assert "query_choice" in res.text

        # 7. Query Choice with Digits=0 (Feedback)
        res = await client.post("/api/v1/telephony/plivo/query_choice", data={"CallUUID": call_uuid, "Digits": "0"})
        assert res.status_code == 200
        assert "feedback" in res.text
        assert session.state == IVRState.FEEDBACK_PENDING

    # Cleanup
    db.delete(booking)
    db.delete(trip)
    db.delete(bus)
    db.delete(route)
    db.delete(user)
    conv = db.query(Conversation).filter_by(session_id=session.session_id).first()
    if conv:
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db.delete(conv)
    db.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
    db.commit()
    db.close()


@pytest.mark.asyncio
async def test_telugu_telephony_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    phone_number = "7036510611"
    email = "telugu_telephony_tester@example.com"
    booking_code = "BK-TELUGU"

    user = db.query(User).filter_by(email=email).first()
    if user:
        db.delete(user)
        db.commit()

    user = User(
        id=uuid.uuid4(),
        full_name="Telugu Telephony Tester",
        email=email,
        phone=phone_number,
        password_hash="pass",
        role=UserRole.CUSTOMER,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()

    route = Route(source_city="Delhi", destination_city="Hyderabad", distance_km=1500, estimated_duration_minutes=1200)
    db.add(route)
    db.commit()

    bus = Bus(bus_number="BUSTEL", bus_name="Telugu Express", registration_number="TELU123", capacity=36, bus_type=BusType.AC_SLEEPER)
    db.add(bus)
    db.commit()

    departure_time = datetime.now() + timedelta(days=2)
    trip = Trip(
        route_id=route.id,
        bus_id=bus.id,
        departure_time=departure_time,
        arrival_time=departure_time + timedelta(hours=15),
        status=TripStatus.SCHEDULED,
        available_seats=30
    )
    db.add(trip)
    db.commit()

    booking = Booking(
        booking_code=booking_code,
        user_id=user.id,
        trip_id=trip.id,
        seat_number="T1",
        booking_status=BookingStatus.CONFIRMED,
        payment_status=PaymentStatus.PAID
    )
    db.add(booking)
    db.commit()

    call_uuid = f"CA-TeluguTest-{uuid.uuid4().hex[:6]}"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Incoming Call
        res = await client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": phone_number})
        assert res.status_code == 200

        # 2. Select Telugu (Digits=3)
        res = await client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "3"})
        assert res.status_code == 200
        session = ivr_manager.calls[call_uuid]
        assert session.language == "te"

        # 3. Enter Booking Code (BK-TELUGU)
        res = await client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
        assert res.status_code == 200
        assert session.state == IVRState.ACTIVE_AGENT
        assert session.language == "te"

        # 4. Ask about refund status in Telugu
        res = await client.post("/api/v1/telephony/plivo/agent", data={"CallUUID": call_uuid, "SpeechResult": "నా రిఫండ్ సమాచారం ఏంటి?"})
        assert res.status_code == 200
        assert "query_choice" in res.text

    # Cleanup
    db.delete(booking)
    db.delete(trip)
    db.delete(bus)
    db.delete(route)
    db.delete(user)
    conv = db.query(Conversation).filter_by(session_id=session.session_id).first()
    if conv:
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db.delete(conv)
    db.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
    db.commit()
    db.close()
