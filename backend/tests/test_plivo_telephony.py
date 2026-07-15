import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta

# Add backend directory to sys.path
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
from app.database.models.conversation import Conversation, ConversationStatus
from app.database.models.conversation_message import ConversationMessage
from app.database.models.customer_feedback import CustomerFeedback
from app.voice.ivr import ivr_manager, IVRState


async def test_plivo_integration():
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

        # Instantiate async httpx client
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # ----------------------------------------------------
            # 1. Incoming Call Webhook (RECORDING_CONSENT_PENDING)
            # ----------------------------------------------------
            print("\n--- 1. Testing Incoming Call Webhook ---")
            response = await client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": caller_phone})
            assert response.status_code == 200
            assert "application/xml" in response.headers["content-type"]
            assert "<GetInput" in response.text
            assert "consent" in response.text
            print("-> Incoming call Plivo XML response: PASSED")

            # ----------------------------------------------------
            # 2. Consent Hook (Redirects to Language Selection)
            # ----------------------------------------------------
            print("\n--- 2. Testing Consent Hook (Redirects to Language Selection) ---")
            response = await client.post("/api/v1/telephony/plivo/consent", data={"CallUUID": call_uuid, "Digits": "1"})
            assert response.status_code == 200
            assert "language" in response.text
            print("-> Consent XML redirects to language selection response: PASSED")

            # ----------------------------------------------------
            # 4. Language Selection Hook (VERIFICATION_PENDING)
            # ----------------------------------------------------
            print("\n--- 4. Testing Language Selection Hook ---")
            response = await client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "1"})
            assert response.status_code == 200
            assert "verify_code" in response.text
            print("-> Language selection redirects to booking verify code: PASSED")

            # ----------------------------------------------------
            # 5. Verify Code (ACTIVE_AGENT)
            # ----------------------------------------------------
            print("\n--- 5. Testing Verify Code Hook (Booking Ownership) ---")
            response = await client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
            assert response.status_code == 200
            assert "agent" in response.text
            
            # Verify call session state is now ACTIVE_AGENT
            session = ivr_manager.calls[call_uuid]
            assert session.state == IVRState.ACTIVE_AGENT
            assert session.user_id == str(user.id)
            print("-> Booking ownership verification XML response: PASSED")

            # ----------------------------------------------------
            # 6. Active Agent turn (Speech -> Play AI response + choice menu)
            # ----------------------------------------------------
            print("\n--- 6. Testing Active Agent Voice Turn ---")
            
            # Simulate active conversation resolved intent
            conv = db.query(Conversation).filter_by(session_id=session.session_id).first()
            assert conv is not None
            conv.resolution_status = "resolved"
            db.commit()

            # Call agent turn with speech - should ask for continue/end query choice
            response = await client.post("/api/v1/telephony/plivo/agent", data={"CallUUID": call_uuid, "Speech": "Check my booking."})
            assert response.status_code == 200
            assert "query_choice" in response.text
            print("-> Active agent voice turn choice query redirect XML response: PASSED")

            # ----------------------------------------------------
            # 7. Query Choice selection (Digits=0 transitions to FEEDBACK_PENDING)
            # ----------------------------------------------------
            print("\n--- 7. Testing Query Choice Hook (digits=0) ---")
            response = await client.post("/api/v1/telephony/plivo/query_choice", data={"CallUUID": call_uuid, "Digits": "0"})
            assert response.status_code == 200
            assert "feedback" in response.text
            assert session.state == IVRState.FEEDBACK_PENDING
            print("-> Choice resolved to feedback transition response: PASSED")

            # ----------------------------------------------------
            # 8. CSAT Rating collection (0 maps to 10, or 10 maps to 10)
            # ----------------------------------------------------
            print("\n--- 8. Testing CSAT Feedback collection ---")
            response = await client.post("/api/v1/telephony/plivo/feedback", data={"CallUUID": call_uuid, "Digits": "0"})
            assert response.status_code == 200
            assert "<Hangup" in response.text
            
            # Assert call is completed
            assert session.state == IVRState.COMPLETED
            
            # Verify rating database row created
            fb = db.query(CustomerFeedback).filter_by(conversation_id=conv.id).first()
            assert fb is not None
            assert fb.rating == 10
            print("-> Customer rating persisted as 10 XML response: PASSED")

            # ----------------------------------------------------
            # 9. Call Recording Status Callback mapping
            # ----------------------------------------------------
            print("\n--- 9. Testing Recording Completed Callback ---")
            recording_url = "https://api.plivo.com/v1/Account/MA/Recordings/RE12345"
            response = await client.post(
                "/api/v1/telephony/plivo/recording-callback",
                data={"CallUUID": call_uuid, "RecordingUrl": recording_url}
            )
            assert response.status_code == 200
            
            # Verify recording URL stored in database
            db.refresh(conv)
            assert conv.recording_url == recording_url
            print("-> Recording URL correctly saved to conversation database record: PASSED")

            # ----------------------------------------------------
            # 10. Status Callback Disconnect Hook
            # ----------------------------------------------------
            print("\n--- 10. Testing Disconnect Status Callbacks ---")
            session.state = IVRState.ACTIVE_AGENT
            session._save_to_db()
            
            response = await client.post("/api/v1/telephony/plivo/hangup", data={"CallUUID": call_uuid, "HangupCause": "Normal Hangup"})
            assert response.status_code == 200
            
            # Refresh and check completed
            assert session.state == IVRState.COMPLETED
            print("-> Hangup callback completed disconnect flow: PASSED")

        # Database Cleanup
        print("\nCleaning up database records...")
        db.delete(booking)
        db.query(Trip).filter(Trip.route_id == route.id).delete()
        db.commit()
        db.delete(bus)
        db.delete(route)
        db.delete(user)
        db.query(IvrSession).filter(IvrSession.call_id == call_uuid).delete()
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()
        print("Cleanup completed.")

        print("\nALL PLIVO TELEPHONY INTEGRATION TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        db.close()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_plivo_integration())
    if not success:
        sys.exit(1)
