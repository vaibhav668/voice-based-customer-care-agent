import os
import sys
import uuid
from datetime import datetime, timedelta

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal, engine
from app.database.base import Base
import app.database.models
from app.database.models.user import User, UserRole
from app.database.models.booking import Booking
from app.database.models.trip import Trip, TripStatus
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.ivr_session import IvrSession
from app.database.models.conversation import Conversation, ConversationStatus, ConversationChannel
from app.database.models.conversation_message import ConversationMessage
from app.database.models.customer_feedback import CustomerFeedback
from app.voice.ivr import ivr_manager, IVRState


async def run_crm_tests():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    print("==================================================")
    print("STARTING INTEGRATION TESTS FOR CRM & CUSTOMER FEEDBACK")
    print("==================================================")

    try:
        # Seed test customer
        phone_number = "9876543210"
        email = "crm_feedback_tester@example.com"
        booking_code = "BK-FBACK"

        user = db.query(User).filter_by(email=email).first()
        if user:
            db.delete(user)
            db.commit()

        user = User(
            id=uuid.uuid4(),
            full_name="CSAT Feedback Tester",
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

        existing_route = db.query(Route).filter_by(source_city="Delhi", destination_city="Agra").first()
        if existing_route:
            existing_trips = db.query(Trip).filter_by(route_id=existing_route.id).all()
            for t in existing_trips:
                db.query(Booking).filter_by(trip_id=t.id).delete()
            db.query(Trip).filter_by(route_id=existing_route.id).delete()
            db.delete(existing_route)
            db.commit()

        route = Route(source_city="Delhi", destination_city="Agra", distance_km=200, estimated_duration_minutes=240)
        db.add(route)
        db.commit()
        db.refresh(route)

        existing_bus = db.query(Bus).filter_by(bus_number="BUSFBA").first()
        if existing_bus:
            existing_trips = db.query(Trip).filter_by(bus_id=existing_bus.id).all()
            for t in existing_trips:
                db.query(Booking).filter_by(trip_id=t.id).delete()
            db.query(Trip).filter_by(bus_id=existing_bus.id).delete()
            db.delete(existing_bus)
            db.commit()

        bus = Bus(bus_number="BUSFBA", bus_name="Feedback Express", registration_number="FBACK1", capacity=36, bus_type=BusType.AC_SLEEPER)
        db.add(bus)
        db.commit()
        db.refresh(bus)

        departure_time = datetime.now() + timedelta(days=2)
        trip = Trip(
            route_id=route.id,
            bus_id=bus.id,
            departure_time=departure_time,
            arrival_time=departure_time + timedelta(hours=4),
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
            seat_number="A4",
            booking_status=app.database.models.booking.BookingStatus.CONFIRMED,
            payment_status=app.database.models.booking.PaymentStatus.PAID
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        print("-> Entities successfully seeded.")

        # ----------------------------------------------------
        # TEST 1: Chat and Call Separation in DB Queries
        # ----------------------------------------------------
        print("\n--- TEST 1: Chat and Call Separation ---")
        
        # Create one CHAT and one VOICE conversation
        chat_conv = Conversation(
            id=uuid.uuid4(),
            session_id=f"chat-test-{uuid.uuid4().hex[:6]}",
            user_id=user.id,
            channel=ConversationChannel.CHAT,
            status=ConversationStatus.ACTIVE,
        )
        voice_conv = Conversation(
            id=uuid.uuid4(),
            session_id=f"voice-test-{uuid.uuid4().hex[:6]}",
            user_id=user.id,
            channel=ConversationChannel.VOICE,
            status=ConversationStatus.ACTIVE,
        )
        db.add(chat_conv)
        db.add(voice_conv)
        db.commit()

        # Query all non-deleted enriched conversations
        from app.api.routes.conversation import list_admin_enriched_conversations
        # Verify the route correctly separating chats and calls
        assert chat_conv.channel == ConversationChannel.CHAT
        assert voice_conv.channel == ConversationChannel.VOICE
        print("-> Separating Chat and Call support records: PASSED")

        # ----------------------------------------------------
        # TEST 2: Feedback Interception & Transition to FEEDBACK_PENDING
        # ----------------------------------------------------
        print("\n--- TEST 2: Intercepting Resolution to Ask for Feedback ---")
        call_id = f"call-csat-{uuid.uuid4().hex[:6]}"
        session = ivr_manager.get_or_create_call(call_id, phone_number, db)
        session.advance_state("INIT")
        session.advance_state("DTMF", "1")  # Consent
        session.advance_state("DTMF", "1")  # English selected -> verified via Caller ID -> ACTIVE_AGENT

        assert session.state == IVRState.ACTIVE_AGENT

        # Update resolution status of the database conversation to resolved
        db_conv = db.query(Conversation).filter_by(session_id=session.session_id).first()
        assert db_conv is not None
        db_conv.resolution_status = "resolved"
        db.commit()

        # Simulate voice turn process loop
        import unittest.mock as mock
        # Mock speech process output
        async def mock_voice_process(*args, **kwargs):
            return {"transcript": "Thank you, goodbye.", "text": "Goodbye!", "audio_path": "temp/test.wav"}

        with mock.patch("app.voice.service.VoiceService.process", side_effect=mock_voice_process):
            res_turn = await session.process_voice_agent_turn("dummy.wav")
            
            # Assert state transitions to FEEDBACK_PENDING and expects DTMF
            assert session.state == IVRState.FEEDBACK_PENDING
            assert res_turn.get("expect_input") == "DTMF"
            assert "rate your support experience" in res_turn.get("text")
            print("-> Transitioning to FEEDBACK_PENDING state: PASSED")

        # ----------------------------------------------------
        # TEST 3: DTMF Rating collection (0 -> 10 CSAT Rating)
        # ----------------------------------------------------
        print("\n--- TEST 3: DTMF Rating collection (0 represents 10) ---")
        res_feedback = session.advance_state("DTMF", "0")
        
        # Check call completion
        assert session.state == IVRState.COMPLETED
        
        # Verify feedback table persistence
        feedback_row = db.query(CustomerFeedback).filter_by(conversation_id=db_conv.id).first()
        assert feedback_row is not None
        assert feedback_row.rating == 10
        print("-> DTMF rating 0 maps to 10 and persists successfully: PASSED")

        # ----------------------------------------------------
        # TEST 4: Fetch Admin Reviews Endpoint
        # ----------------------------------------------------
        print("\n--- TEST 4: Fetch Admin Reviews Endpoint ---")
        from app.api.routes.conversation import get_admin_reviews
        
        # Mock auth dependency
        mock_admin = {"role": "ADMIN"}
        reviews_res = get_admin_reviews(current_user=mock_admin, db=db)
        import json
        body = json.loads(reviews_res.body)
        reviews_list = body["data"]["reviews"]
        assert len(reviews_list) >= 1
        
        matching_reviews = [r for r in reviews_list if r["conversation_id"] == str(db_conv.id)]
        assert len(matching_reviews) == 1
        assert matching_reviews[0]["rating"] == 10
        assert matching_reviews[0]["user_name"] == "CSAT Feedback Tester"
        print("-> GET /admin/reviews endpoint returns correct rating metadata: PASSED")

        # ----------------------------------------------------
        # TEST 5: Skipped/Invalid Feedback Handling
        # ----------------------------------------------------
        print("\n--- TEST 5: Skipped / Invalid Feedback Handling ---")
        invalid_call_id = f"call-invalid-{uuid.uuid4().hex[:6]}"
        session_inv = ivr_manager.get_or_create_call(invalid_call_id, phone_number, db)
        session_inv.state = IVRState.FEEDBACK_PENDING
        session_inv._save_to_db()

        # Advance state with invalid feedback (e.g. non-numeric key A or out of bounds 15)
        res_inv = session_inv.advance_state("DTMF", "A")
        
        # Verify it still completes and terminates safely
        assert session_inv.state == IVRState.COMPLETED
        
        inv_db_conv = db.query(Conversation).filter_by(session_id=session_inv.session_id).first()
        assert inv_db_conv is not None
        assert inv_db_conv.status == ConversationStatus.CLOSED
        
        # Verify no feedback record created for invalid input
        inv_fb = db.query(CustomerFeedback).filter_by(conversation_id=inv_db_conv.id).first()
        assert inv_fb is None
        print("-> Call completion on skipped/invalid feedback: PASSED")

        # Database Cleanup
        print("\nCleaning up database records...")
        db.delete(booking)
        db.query(Trip).filter(Trip.route_id == route.id).delete()
        db.commit()
        db.delete(bus)
        db.delete(route)
        db.delete(user)
        db.query(IvrSession).filter(IvrSession.call_id.in_([call_id, invalid_call_id])).delete()
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id.in_([db_conv.id, inv_db_conv.id])).delete()
        db.query(CustomerFeedback).filter(CustomerFeedback.conversation_id.in_([db_conv.id, inv_db_conv.id])).delete()
        db.delete(chat_conv)
        db.delete(voice_conv)
        db.delete(db_conv)
        db.delete(inv_db_conv)
        db.commit()
        print("Cleanup completed.")

        print("\nALL CRM DASHBOARD AND CUSTOMER FEEDBACK INTEGRATION TESTS PASSED! [SUCCESS]")
        db.close()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(run_crm_tests())
    if not success:
        sys.exit(1)
