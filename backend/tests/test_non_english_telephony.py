import os
import sys
import uuid
import pytest
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
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


def test_non_english_hindi_telephony_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    phone_number = "9876543211"
    email = "hindi_telephony_tester@example.com"
    booking_code = "BK-HINDI"

    # Clean existing user
    user = db.query(User).filter_by(email=email).first()
    if user:
        db.delete(user)
        db.commit()

    # Clean existing bus
    existing_bus = db.query(Bus).filter_by(bus_number="BUSHIN").first()
    if existing_bus:
        existing_trips = db.query(Trip).filter_by(bus_id=existing_bus.id).all()
        for t in existing_trips:
            db.query(Booking).filter_by(trip_id=t.id).delete()
        db.query(Trip).filter_by(bus_id=existing_bus.id).delete()
        db.delete(existing_bus)
        db.commit()

    # Clean existing route
    existing_route = db.query(Route).filter_by(source_city="Delhi", destination_city="Goa").first()
    if existing_route:
        existing_trips = db.query(Trip).filter_by(route_id=existing_route.id).all()
        for t in existing_trips:
            db.query(Booking).filter_by(trip_id=t.id).delete()
        db.query(Trip).filter_by(route_id=existing_route.id).delete()
        db.delete(existing_route)
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

    # Save seeded entity IDs and close DB session to prevent locks during ASGI request processing
    user_id_str = str(user.id)
    booking_id = booking.id
    trip_id = trip.id
    bus_id = bus.id
    route_id = route.id
    db.close()

    with TestClient(app) as client:
        # 1. Incoming Call
        res = client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": phone_number})
        assert res.status_code == 200
        assert "language" in res.text

        # 2. Select Hindi (Digits=2)
        res = client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "2"})
        assert res.status_code == 200
        session = ivr_manager.calls[call_uuid]
        assert session.language == "hi"
        assert "verify_code" in res.text

        # 3. Enter Booking Code (BK-HINDI)
        res = client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
        assert res.status_code == 200
        assert session.state == IVRState.ACTIVE_AGENT
        assert session.language == "hi"
        assert "Stream" in res.text
        assert "bidirectional" in res.text

        # 4. Connect to Bidirectional WebSocket Stream
        with client.websocket_connect(f"/api/v1/telephony/plivo/stream?call_uuid={call_uuid}") as ws:
            ws.send_json({
                "event": "start",
                "streamId": "STR-HINDI-123",
                "start": {
                    "callUuid": call_uuid
                }
            })
            # Receive welcome prompt response stream events
            resp = ws.receive_json()
            assert resp["event"] == "playAudio"
            assert resp["media"]["contentType"] == "audio/x-mulaw"
            assert resp["media"]["sampleRate"] == "8000"
            assert "payload" in resp["media"]

    # Cleanup
    db_cleanup = SessionLocal()
    db_cleanup.query(Booking).filter(Booking.id == booking_id).delete()
    db_cleanup.query(Trip).filter(Trip.id == trip_id).delete()
    db_cleanup.query(Bus).filter(Bus.id == bus_id).delete()
    db_cleanup.query(Route).filter(Route.id == route_id).delete()
    db_cleanup.query(User).filter(User.id == uuid.UUID(user_id_str)).delete()
    conv = db_cleanup.query(Conversation).filter_by(session_id=session.session_id).first()
    if conv:
        db_cleanup.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db_cleanup.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db_cleanup.delete(conv)
    db_cleanup.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
    db_cleanup.commit()
    db_cleanup.close()


def test_telugu_telephony_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    phone_number = "7036510611"
    email = "telugu_telephony_tester@example.com"
    booking_code = "BK-TELUGU"

    # Clean existing user
    user = db.query(User).filter_by(email=email).first()
    if user:
        db.delete(user)
        db.commit()

    # Clean existing bus
    existing_bus = db.query(Bus).filter_by(bus_number="BUSTEL").first()
    if existing_bus:
        existing_trips = db.query(Trip).filter_by(bus_id=existing_bus.id).all()
        for t in existing_trips:
            db.query(Booking).filter_by(trip_id=t.id).delete()
        db.query(Trip).filter_by(bus_id=existing_bus.id).delete()
        db.delete(existing_bus)
        db.commit()

    # Clean existing route
    existing_route = db.query(Route).filter_by(source_city="Delhi", destination_city="Hyderabad").first()
    if existing_route:
        existing_trips = db.query(Trip).filter_by(route_id=existing_route.id).all()
        for t in existing_trips:
            db.query(Booking).filter_by(trip_id=t.id).delete()
        db.query(Trip).filter_by(route_id=existing_route.id).delete()
        db.delete(existing_route)
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

    # Save seeded entity IDs and close DB session to prevent locks during ASGI request processing
    user_id_str = str(user.id)
    booking_id = booking.id
    trip_id = trip.id
    bus_id = bus.id
    route_id = route.id
    db.close()

    with TestClient(app) as client:
        # 1. Incoming Call
        res = client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": phone_number})
        assert res.status_code == 200

        # 2. Select Telugu (Digits=3)
        res = client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "3"})
        assert res.status_code == 200
        session = ivr_manager.calls[call_uuid]
        assert session.language == "te"

        # 3. Enter Booking Code (BK-TELUGU)
        res = client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
        assert res.status_code == 200
        assert session.state == IVRState.ACTIVE_AGENT
        assert session.language == "te"
        assert "Stream" in res.text
        assert "bidirectional" in res.text

        # 4. Connect to Bidirectional WebSocket Stream
        with client.websocket_connect(f"/api/v1/telephony/plivo/stream?call_uuid={call_uuid}") as ws:
            ws.send_json({
                "event": "start",
                "streamId": "STR-TELUGU-123",
                "start": {
                    "callUuid": call_uuid
                }
            })
            # Receive welcome prompt response stream events
            resp = ws.receive_json()
            assert resp["event"] == "playAudio"
            assert resp["media"]["contentType"] == "audio/x-mulaw"
            assert resp["media"]["sampleRate"] == "8000"
            assert "payload" in resp["media"]

    # Cleanup
    db_cleanup = SessionLocal()
    db_cleanup.query(Booking).filter(Booking.id == booking_id).delete()
    db_cleanup.query(Trip).filter(Trip.id == trip_id).delete()
    db_cleanup.query(Bus).filter(Bus.id == bus_id).delete()
    db_cleanup.query(Route).filter(Route.id == route_id).delete()
    db_cleanup.query(User).filter(User.id == uuid.UUID(user_id_str)).delete()
    conv = db_cleanup.query(Conversation).filter_by(session_id=session.session_id).first()
    if conv:
        db_cleanup.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db_cleanup.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db_cleanup.delete(conv)
    db_cleanup.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
    db_cleanup.commit()
    db_cleanup.close()
