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
from app.database.models.conversation import Conversation, ConversationStatus
from app.database.models.conversation_message import ConversationMessage
from app.voice.ivr import ivr_manager, IVRState
from app.ai.tools.complaint import ComplaintTool
from app.exceptions.common import NotFoundException


def run_tests():
    # Make sure DB schema is created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    print("==================================================")
    print("STARTING CALL LIFECYCLE, SECURITY & CRM FLOW TESTS")
    print("==================================================")

    try:
        # Cleanup past test data
        phone_number = "9876543210"
        email = "crm_tester@example.com"
        booking_code = "BK-CRM88"

        user = db.query(User).filter_by(email=email).first()
        if user:
            db.delete(user)
            db.commit()

        user = User(
            id=uuid.uuid4(),
            full_name="CRM Lifecycle Tester",
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

        route = Route(source_city="Mumbai", destination_city="Pune", distance_km=150, estimated_duration_minutes=180)
        db.add(route)
        db.commit()
        db.refresh(route)

        bus = Bus(bus_number="BUSCRM", bus_name="CRM Express", registration_number="REGLIF", capacity=36, bus_type=BusType.AC_SLEEPER)
        db.add(bus)
        db.commit()
        db.refresh(bus)

        departure_time = datetime.now() + timedelta(days=3)
        trip = Trip(
            route_id=route.id,
            bus_id=bus.id,
            departure_time=departure_time,
            arrival_time=departure_time + timedelta(hours=3),
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
            seat_number="B12",
            booking_status=app.database.models.booking.BookingStatus.CONFIRMED,
            payment_status=app.database.models.booking.PaymentStatus.PAID
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        print("-> Database entities seeded successfully.")

        # ----------------------------------------------------
        # TEST 1: Database-backed Session Persistence
        # ----------------------------------------------------
        print("\n--- TEST 1: Database-backed Session Persistence ---")
        call_id = f"call-persistent-{uuid.uuid4().hex[:6]}"
        
        # Start call session
        session = ivr_manager.get_or_create_call(call_id, phone_number, db)
        assert session.state == IVRState.INCOMING
        
        # advance state
        res = session.advance_state("INIT")
        assert session.state == IVRState.RECORDING_CONSENT_PENDING
        
        # Verify persistence in IvrSession table
        row = db.query(IvrSession).filter_by(call_id=call_id).first()
        assert row is not None
        assert row.state == "RECORDING_CONSENT_PENDING"
        
        # Simulate instance restart: clear manager cache and reload from DB
        del ivr_manager.calls[call_id]
        session_reloaded = ivr_manager.get_or_create_call(call_id, phone_number, db)
        assert session_reloaded.state == IVRState.RECORDING_CONSENT_PENDING
        print("-> Session persistence validation: PASSED")

        # ----------------------------------------------------
        # TEST 2: Two-Step Caller Verification
        # ----------------------------------------------------
        print("\n--- TEST 2: Two-Step Caller Verification ---")
        unverified_call_id = f"call-unverified-{uuid.uuid4().hex[:6]}"
        unverified_phone = "9998887776"
        
        session_unv = ivr_manager.get_or_create_call(unverified_call_id, unverified_phone, db)
        session_unv.advance_state("INIT")
        session_unv.advance_state("DTMF", "1") # Accept consent
        res = session_unv.advance_state("DTMF", "1") # English selected -> verification pending
        assert session_unv.state == IVRState.VERIFICATION_PENDING
        
        # Step 2.1: Input correct booking code -> transition to phone pending
        res = session_unv.advance_state("DTMF", booking_code)
        assert session_unv.state == IVRState.VERIFICATION_PHONE_PENDING
        print("Two-step verification - Part 1 (Booking Code): PASSED")
        
        # Step 2.2: Input incorrect phone number -> fail
        res = session_unv.advance_state("DTMF", "0000000000")
        assert session_unv.state == IVRState.VERIFICATION_PHONE_PENDING
        assert "Verification failed" in res.get("prompt")
        
        # Step 2.3: Input correct phone number -> Active Agent
        res = session_unv.advance_state("DTMF", phone_number)
        assert session_unv.state == IVRState.ACTIVE_AGENT
        assert session_unv.user_id == str(user.id)
        print("Two-step verification - Part 2 (Owner Phone): PASSED")

        # ----------------------------------------------------
        # TEST 3: Turn-by-Turn Events Logging
        # ----------------------------------------------------
        print("\n--- TEST 3: Turn-by-Turn Events Logging ---")
        conv = db.query(Conversation).filter_by(session_id=session_unv.session_id).first()
        assert conv is not None
        
        # Load messages
        messages = db.query(ConversationMessage).filter_by(conversation_id=conv.id).order_by(ConversationMessage.created_at.asc()).all()
        system_msgs = [m for m in messages if m.sender.value == "SYSTEM"]
        
        print(f"Recorded {len(system_msgs)} system events during the call:")
        for sm in system_msgs:
            print(f" - [SYSTEM EVENT] {sm.message}")
            
        assert len(system_msgs) >= 4
        print("-> Call event logs persistence: PASSED")

        # ----------------------------------------------------
        # TEST 4: Tool Security & Ownership Verification
        # ----------------------------------------------------
        print("\n--- TEST 4: Tool Security & Ownership Verification ---")
        complaint_tool = ComplaintTool(db)
        
        # Try to register a complaint with an unauthorized user ID
        unauthorized_user_id = str(uuid.uuid4())
        try:
            complaint_tool.execute(
                booking_code=booking_code,
                complaint="Bus was late.",
                user_id=unauthorized_user_id,
            )
            print("FAILED: Allowed unauthorized complaint registration!")
            assert False
        except NotFoundException as e:
            print("Success: Correctly raised NotFoundException for unauthorized user ID:", e)
            
        # Try with incorrect phone number
        try:
            complaint_tool.execute(
                booking_code=booking_code,
                complaint="Late arrival.",
                session_phone="9999999999",
            )
            print("FAILED: Allowed unauthorized complaint registration with mismatched phone number!")
            assert False
        except NotFoundException as e:
            print("Success: Correctly raised NotFoundException for unauthorized phone number:", e)
            
        # Try with correct credentials
        res_complaint = complaint_tool.execute(
            booking_code=booking_code,
            complaint="Super late.",
            user_id=str(user.id)
        )
        assert res_complaint.get("complaint_code") is not None
        print("Success: Authorized complaint successfully registered.")
        print("-> Tool Security checks: PASSED")

        # ----------------------------------------------------
        # TEST 5: Call Completion & Resolution tracking
        # ----------------------------------------------------
        print("\n--- TEST 5: Call Completion ---")
        
        # Verify call is ACTIVE
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.ended_at is None
        
        # Complete the call
        session_unv.complete_call()
        
        db.refresh(conv)
        assert conv.status == ConversationStatus.CLOSED
        assert conv.ended_at is not None
        print(f"Call closed successfully. Ended at: {conv.ended_at}")
        print("-> Call Completion & Resolution Status tracking: PASSED")

        # Database Cleanup
        print("\nCleaning up database records...")
        db.delete(booking)
        db.query(Trip).filter(Trip.route_id == route.id).delete()
        db.commit()
        db.delete(bus)
        db.delete(route)
        db.delete(user)
        db.query(IvrSession).filter(IvrSession.call_id.in_([call_id, unverified_call_id])).delete()
        db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()
        print("Cleanup completed.")

        print("\nALL LIFECYCLE, SECURITY & REAL-TIME CRM TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        db.close()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
