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


async def test_twilio_integration():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    print("==================================================")
    print("STARTING TWILIO TELEPHONY INTEGRATION WEBHOOK TESTS")
    print("==================================================")

    try:
        # Seed test customer
        phone_number = "9876543210"
        email = "twilio_telephony_tester@example.com"
        booking_code = "BK-TWILI"

        user = db.query(User).filter_by(email=email).first()
        if user:
            db.delete(user)
            db.commit()

        user = User(
            id=uuid.uuid4(),
            full_name="Twilio Telephony Tester",
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

        existing_bus = db.query(Bus).filter_by(bus_number="BUSTWI").first()
        if existing_bus:
            existing_trips = db.query(Trip).filter_by(bus_id=existing_bus.id).all()
            for t in existing_trips:
                db.query(Booking).filter_by(trip_id=t.id).delete()
            db.query(Trip).filter_by(bus_id=existing_bus.id).delete()
            db.delete(existing_bus)
            db.commit()

        bus = Bus(bus_number="BUSTWI", bus_name="Twilio Express", registration_number="TWILIF", capacity=36, bus_type=BusType.AC_SLEEPER)
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
        call_sid = f"CA-Test-{uuid.uuid4().hex[:6]}"
        caller_phone = "1234567890" # Unverified phone caller

        # Instantiate async httpx client
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # ----------------------------------------------------
            # 1. Incoming Call Webhook (RECORDING_CONSENT_PENDING)
            # ----------------------------------------------------
            print("\n--- 1. Testing Incoming Call Webhook ---")
            response = await client.post("/api/v1/telephony/twilio/incoming", data={"CallSid": call_sid, "From": caller_phone})
            assert response.status_code == 200
            assert "application/xml" in response.headers["content-type"]
            assert "<Gather" in response.text
            assert "consent" in response.text
            print("-> Incoming call TwiML response: PASSED")

            # ----------------------------------------------------
            # 2. Consent Hook (LANGUAGE_SELECTION_PENDING)
            # ----------------------------------------------------
            print("\n--- 2. Testing Consent Hook ---")
            response = await client.post("/api/v1/telephony/twilio/consent", data={"CallSid": call_sid, "Digits": "1"})
            assert response.status_code == 200
            assert "language" in response.text
            print("-> Consent TwiML response: PASSED")

            # ----------------------------------------------------
            # 3. Language Selection Hook (VERIFICATION_PENDING)
            # ----------------------------------------------------
            print("\n--- 3. Testing Language Selection Hook ---")
            response = await client.post("/api/v1/telephony/twilio/language", data={"CallSid": call_sid, "Digits": "1"})
            assert response.status_code == 200
            assert "verify_code" in response.text
            print("-> Language selection unverified verification redirect TwiML response: PASSED")

            # ----------------------------------------------------
            # 4. Verify Code (VERIFICATION_PHONE_PENDING)
            # ----------------------------------------------------
            print("\n--- 4. Testing Verify Code Hook ---")
            response = await client.post("/api/v1/telephony/twilio/verify_code", data={"CallSid": call_sid, "Digits": booking_code})
            assert response.status_code == 200
            assert "verify_phone" in response.text
            print("-> Code verification phone lookup redirection TwiML response: PASSED")

            # ----------------------------------------------------
            # 5. Verify Phone (ACTIVE_AGENT)
            # ----------------------------------------------------
            print("\n--- 5. Testing Verify Phone Hook ---")
            response = await client.post("/api/v1/telephony/twilio/verify_phone", data={"CallSid": call_sid, "Digits": phone_number})
            assert response.status_code == 200
            assert "agent" in response.text
            
            # Verify call session state is now ACTIVE_AGENT
            session = ivr_manager.calls[call_sid]
            assert session.state == IVRState.ACTIVE_AGENT
            assert session.user_id == str(user.id)
            print("-> Caller phone two-step verification TwiML response: PASSED")

            # ----------------------------------------------------
            # 6. Active Agent turn (ASR Text input -> TTS Playback)
            # ----------------------------------------------------
            print("\n--- 6. Testing Active Agent Voice Turn ---")
            
            # Simulate active conversation resolved intent
            conv = db.query(Conversation).filter_by(session_id=session.session_id).first()
            assert conv is not None
            conv.resolution_status = "resolved"
            db.commit()

            # Call agent turn, which should intercept resolution and transition to FEEDBACK_PENDING
            response = await client.post("/api/v1/telephony/twilio/agent", data={"CallSid": call_sid, "SpeechResult": "All good thanks."})
            assert response.status_code == 200
            assert "feedback" in response.text
            assert session.state == IVRState.FEEDBACK_PENDING
            print("-> Agent text turn to feedback collection transition TwiML response: PASSED")

            # ----------------------------------------------------
            # 7. CSAT Rating collection (0 maps to 10)
            # ----------------------------------------------------
            print("\n--- 7. Testing CSAT Feedback collection ---")
            response = await client.post("/api/v1/telephony/twilio/feedback", data={"CallSid": call_sid, "Digits": "0"})
            assert response.status_code == 200
            assert "<Hangup" in response.text
            
            # Assert call is completed
            assert session.state == IVRState.COMPLETED
            
            # Verify rating database row created
            fb = db.query(CustomerFeedback).filter_by(conversation_id=conv.id).first()
            assert fb is not None
            assert fb.rating == 10
            print("-> Customer rating persisted as 10 TwiML response: PASSED")

            # ----------------------------------------------------
            # 8. Status Callback Disconnect Hook
            # ----------------------------------------------------
            print("\n--- 8. Testing Disconnect Status Callbacks ---")
            # Ensure status callbacks gracefully end sessions
            session.state = IVRState.ACTIVE_AGENT
            session._save_to_db()
            
            response = await client.post("/api/v1/telephony/twilio/status", data={"CallSid": call_sid, "CallStatus": "completed"})
            assert response.status_code == 200
            
            # Refresh and check completed
            assert session.state == IVRState.COMPLETED
            print("-> Status callback completed disconnect flow: PASSED")

        # Database Cleanup
        print("\nCleaning up database records...")
        db.delete(booking)
        db.query(Trip).filter(Trip.route_id == route.id).delete()
        db.commit()
        db.delete(bus)
        db.delete(route)
        db.delete(user)
        db.query(IvrSession).filter(IvrSession.call_id == call_sid).delete()
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db.query(CustomerFeedback).filter(CustomerFeedback.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()
        print("Cleanup completed.")

        print("\nALL TWILIO TELEPHONY INTEGRATION TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        db.close()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_twilio_integration())
    if not success:
        sys.exit(1)
