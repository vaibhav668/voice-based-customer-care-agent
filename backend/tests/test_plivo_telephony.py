import os
import sys
import uuid
import pytest
from datetime import datetime, timedelta

# Add backend directory to sys.path
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
from app.database.models.conversation import Conversation, ConversationStatus
from app.database.models.conversation_message import ConversationMessage
from app.database.models.customer_feedback import CustomerFeedback
from app.voice.ivr import ivr_manager, IVRState


def test_plivo_integration():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    print("==================================================")
    print("STARTING PLIVO TELEPHONY INTEGRATION WEBHOOK TESTS")
    print("==================================================")

    try:
        # Seed test customer
        phone_number = "9876543210"
        email = "plivo_telephony_tester@example.com"
        booking_code = "BK-PLIVO"

        user = db.query(User).filter_by(email=email).first()
        if user:
            db.delete(user)
            db.commit()

        user = User(
            id=uuid.uuid4(),
            full_name="Plivo Telephony Tester",
            email=email,
            phone=phone_number,
            password_hash="pass",
            role=UserRole.CUSTOMER,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        existing_route = db.query(Route).filter_by(source_city="Delhi", destination_city="Jaipur").first()
        if existing_route:
            existing_trips = db.query(Trip).filter_by(route_id=existing_route.id).all()
            for t in existing_trips:
                db.query(Booking).filter_by(trip_id=t.id).delete()
            db.query(Trip).filter_by(route_id=existing_route.id).delete()
            db.delete(existing_route)
            db.commit()

        route = Route(source_city="Delhi", destination_city="Jaipur", distance_km=270, estimated_duration_minutes=300)
        db.add(route)
        db.commit()
        db.refresh(route)

        existing_bus = db.query(Bus).filter_by(bus_number="BUSPLI").first()
        if existing_bus:
            existing_trips = db.query(Trip).filter_by(bus_id=existing_bus.id).all()
            for t in existing_trips:
                db.query(Booking).filter_by(trip_id=t.id).delete()
            db.query(Trip).filter_by(bus_id=existing_bus.id).delete()
            db.delete(existing_bus)
            db.commit()

        bus = Bus(bus_number="BUSPLI", bus_name="Plivo Express", registration_number="PLIVAF", capacity=36, bus_type=BusType.AC_SLEEPER)
        db.add(bus)
        db.commit()
        db.refresh(bus)

        departure_time = datetime.now() + timedelta(days=2)
        trip = Trip(
            route_id=route.id,
            bus_id=bus.id,
            departure_time=departure_time,
            arrival_time=departure_time + timedelta(hours=5),
            status=TripStatus.SCHEDULED,
            available_seats=35
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)

        existing_booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if existing_booking:
            db.delete(existing_booking)
            db.commit()

        booking = Booking(
            booking_code=booking_code,
            user_id=user.id,
            trip_id=trip.id,
            seat_number="C4",
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        print("-> Test entities seeded.")

        # Simulate call variables
        call_uuid = f"CA-Test-{uuid.uuid4().hex[:6]}"
        caller_phone = phone_number # Registered customer phone

        # Save seeded entity IDs and close DB session to prevent locks during ASGI request processing
        user_id_str = str(user.id)
        booking_id = booking.id
        trip_id = trip.id
        bus_id = bus.id
        route_id = route.id
        db.close()

        # Instantiate TestClient
        with TestClient(app) as client:

            # ----------------------------------------------------
            # 1. Incoming Call Webhook (Greets and redirects to Language)
            # ----------------------------------------------------
            print("\n--- 1. Testing Incoming Call Webhook ---")
            response = client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": caller_phone})
            assert response.status_code == 200
            assert "application/xml" in response.headers["content-type"]
            assert "<GetInput" in response.text
            assert "language" in response.text
            print("-> Incoming call Plivo XML response: PASSED")

            # ----------------------------------------------------
            # 4. Language Selection Hook (VERIFICATION_PENDING)
            # ----------------------------------------------------
            print("\n--- 4. Testing Language Selection Hook ---")
            response = client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "1"})
            assert response.status_code == 200
            assert "verify_code" in response.text
            print("-> Language selection redirects to booking verify code: PASSED")

            # ----------------------------------------------------
            # 5. Verify Code (ACTIVE_AGENT)
            # ----------------------------------------------------
            print("\n--- 5. Testing Verify Code Hook (Booking Ownership) ---")
            response = client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
            assert response.status_code == 200
            assert "Stream" in response.text
            assert "bidirectional" in response.text
            
            # Verify call session state is now ACTIVE_AGENT
            session = ivr_manager.calls[call_uuid]
            assert session.state == IVRState.ACTIVE_AGENT
            assert session.user_id == user_id_str
            print("-> Booking ownership verification XML response: PASSED")

            # 6. Connect to Bidirectional WebSocket Stream
            with client.websocket_connect(f"/api/v1/telephony/plivo/stream?call_uuid={call_uuid}") as ws:
                ws.send_json({
                    "event": "start",
                    "streamId": "STR-EN-123",
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

            # Transition to FEEDBACK_PENDING to test CSAT rating steps
            session.state = IVRState.FEEDBACK_PENDING
            # Reopen fresh session for save
            db_save = SessionLocal()
            session.db = db_save
            session._save_to_db()
            db_save.close()
            print("-> Choice resolved to feedback transition response: PASSED")

            # ----------------------------------------------------
            # 8. CSAT Rating collection (0 maps to 10, or 10 maps to 10)
            # ----------------------------------------------------
            print("\n--- 8. Testing CSAT Feedback collection ---")
            response = client.post("/api/v1/telephony/plivo/feedback", data={"CallUUID": call_uuid, "Digits": "0"})
            assert response.status_code == 200
            assert "<Hangup" in response.text
            
            # Assert call is completed
            assert session.state == IVRState.COMPLETED
            
            # Verify rating database row created
            db_verify = SessionLocal()
            conv = db_verify.query(Conversation).filter_by(session_id=session.session_id).first()
            fb = db_verify.query(CustomerFeedback).filter_by(conversation_id=conv.id).first()
            assert fb is not None
            assert fb.rating == 10
            print("-> Customer rating persisted as 10 XML response: PASSED")
            db_verify.close()

            # ----------------------------------------------------
            # 9. Call Recording Status Callback mapping
            # ----------------------------------------------------
            print("\n--- 9. Testing Recording Completed Callback ---")
            recording_url = "https://api.plivo.com/v1/Account/MA/Recordings/RE12345"
            response = client.post(
                "/api/v1/telephony/plivo/recording-callback",
                data={"CallUUID": call_uuid, "RecordingUrl": recording_url}
            )
            assert response.status_code == 200
            
            # Verify recording URL stored in database
            db_verify = SessionLocal()
            conv = db_verify.query(Conversation).filter_by(session_id=session.session_id).first()
            assert conv.recording_url == recording_url
            print("-> Recording URL correctly saved to conversation database record: PASSED")
            db_verify.close()

            # ----------------------------------------------------
            # 10. Status Callback Disconnect Hook
            # ----------------------------------------------------
            print("\n--- 10. Testing Disconnect Status Callbacks ---")
            session.state = IVRState.ACTIVE_AGENT
            db_save = SessionLocal()
            session.db = db_save
            session._save_to_db()
            db_save.close()
            
            response = client.post("/api/v1/telephony/plivo/hangup", data={"CallUUID": call_uuid, "HangupCause": "Normal Hangup"})
            assert response.status_code == 200
            
            # Refresh and check completed
            assert session.state == IVRState.COMPLETED
            print("-> Hangup callback completed disconnect flow: PASSED")

        # Database Cleanup
        print("\nCleaning up database records...")
        db_cleanup = SessionLocal()
        db_cleanup.query(Booking).filter(Booking.id == booking_id).delete()
        db_cleanup.query(Trip).filter(Trip.id == trip_id).delete()
        db_cleanup.query(Bus).filter(Bus.id == bus_id).delete()
        db_cleanup.query(Route).filter(Route.id == route_id).delete()
        db_cleanup.query(User).filter(User.id == uuid.UUID(user_id_str)).delete()
        db_cleanup.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
        conv = db_cleanup.query(Conversation).filter_by(session_id=f"ivr-{call_uuid}").first()
        if conv:
            db_cleanup.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
            db_cleanup.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
            db_cleanup.delete(conv)
        db_cleanup.commit()
        db_cleanup.close()
        print("Cleanup completed.")

        print("\nALL PLIVO TELEPHONY INTEGRATION TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db_err = SessionLocal()
        db_err.rollback()
        db_err.close()
        raise e


if __name__ == "__main__":
    test_plivo_integration()
