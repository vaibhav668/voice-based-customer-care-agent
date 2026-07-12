import os
import sys
import uuid
from datetime import datetime, date, timedelta

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
from app.services.booking_service import BookingService
from app.repositories.booking_repository import BookingRepository
from app.repositories.trip_repository import TripRepository
from app.voice.ivr import ivr_manager, IVRState


def run_tests():
    # Make sure DB schema is created
    Base.metadata.create_all(bind=engine)
    
    # Run migrations
    try:
        from migrate import run_migrations
        run_migrations()
    except Exception:
        pass

    db = SessionLocal()
    print("==================================================")
    print("STARTING VOICE CALL IVR & RESCHEDULING FLOW TESTS")
    print("==================================================")

    try:
        # 1. Clean / Setup verified user and booking
        phone_number = "9900990099"
        email = "ivr_tester@example.com"
        
        user = db.query(User).filter_by(email=email).first()
        if user:
            db.delete(user)
            db.commit()
            
        user = User(
            id=uuid.uuid4(),
            full_name="IVR Flow Tester",
            email=email,
            phone=phone_number,
            password_hash="fakehash",
            role=UserRole.CUSTOMER,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Idempotent cleanup of existing test records
        booking_code = "BK-TEST99"
        existing_booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if existing_booking:
            db.delete(existing_booking)
            db.commit()

        # Delete existing trips/buses/routes from previous failed test runs
        db.query(Trip).filter(Trip.bus_id.in_(db.query(Bus.id).filter_by(bus_number="TEST999"))).delete(synchronize_session=False)
        db.query(Bus).filter_by(bus_number="TEST999").delete()
        db.query(Route).filter_by(source_city="Delhi", destination_city="Jaipur").delete()
        db.commit()

        # Create a route & bus
        route = Route(source_city="Delhi", destination_city="Jaipur", distance_km=280, estimated_duration_minutes=300)
        db.add(route)
        db.commit()
        db.refresh(route)

        bus = Bus(bus_number="TEST999", bus_name="Test Volvo", registration_number="REG999", capacity=36, bus_type=BusType.AC_SLEEPER)
        db.add(bus)
        db.commit()
        db.refresh(bus)

        # Create scheduled trip (at least 2 days in the future to allow rescheduling)
        departure_time = datetime.now().replace(hour=18, minute=30, second=0, microsecond=0) + timedelta(days=2)
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

        # Create booking BK-TEST99
        booking_code = "BK-TEST99"
        existing_booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if existing_booking:
            db.delete(existing_booking)
            db.commit()

        booking = Booking(
            booking_code=booking_code,
            user_id=user.id,
            trip_id=trip.id,
            seat_number="A07",
            booking_status=app.database.models.booking.BookingStatus.CONFIRMED,
            payment_status=app.database.models.booking.PaymentStatus.PAID
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        # Verify initial database state matches setup
        print("-> Setup completed successfully.")
        print(f"-> Booking code: {booking_code}")
        print(f"-> User phone: {phone_number}")

        # ----------------------------------------------------
        # TEST 1: Rescheduling Eligibility & Execution
        # ----------------------------------------------------
        print("\n--- TEST 1: Booking Rescheduling execution ---")
        repo = BookingRepository(db)
        service = BookingService(repo)
        
        # Test 1.1: Eligibility check via tool
        from app.ai.tools.reschedule import RescheduleTool
        reschedule_tool = RescheduleTool(db)
        details = reschedule_tool.execute(booking_code=booking_code, user_id=user.id)
        print("Reschedule eligibility response:", details.get("message").replace("₹", "Rs. "))
        assert details.get("reschedule_eligible") is True
        assert details.get("status") == "date_required"

        # Test 1.2: Confirmed execution of rescheduling
        target_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        res = reschedule_tool.execute(
            booking_code=booking_code,
            travel_date=target_date,
            confirmation="yes",
            user_id=user.id
        )
        print("Reschedule execution response:", res.get("message").replace("₹", "Rs. "))
        assert res.get("status") == "rescheduled"
        
        # Check database update
        db.refresh(booking)
        new_trip = db.query(Trip).get(booking.trip_id)
        print(f"New trip departure date: {new_trip.departure_time.strftime('%Y-%m-%d')}")
        assert new_trip.departure_time.strftime("%Y-%m-%d") == target_date
        print("-> Rescheduling Execution: PASSED")

        # ----------------------------------------------------
        # TEST 2: Provider-Independent IVR call flow
        # ----------------------------------------------------
        print("\n--- TEST 2: IVR Call state machine flow ---")
        call_id = f"call-test-{uuid.uuid4().hex[:6]}"
        
        # Test 2.1: Initiate Call with verified caller ID
        print(f"Initiating call for phone: {phone_number}...")
        session = ivr_manager.get_or_create_call(call_id, phone_number, db)
        assert session.state == IVRState.INCOMING
        assert session.user_id == str(user.id)
        
        # Transition out of incoming
        res = session.advance_state("INIT")
        print("State transition response:", res)
        assert session.state == IVRState.RECORDING_CONSENT_PENDING
        assert "may be recorded" in res.get("prompt").lower()

        # Test 2.2: Send DTMF 1 for consent
        print("Sending DTMF 1 (consent)...")
        res = session.advance_state("DTMF", "1")
        print("State transition response:", res)
        assert session.state == IVRState.LANGUAGE_SELECTION_PENDING
        assert session.recording_consent is True

        # Test 2.3: Send DTMF 1 for English (Auto-Verify matches user)
        print("Sending DTMF 1 (English language)...")
        res = session.advance_state("DTMF", "1")
        print("State transition response:", res)
        assert session.state == IVRState.ACTIVE_AGENT
        assert session.language == "en"
        assert "Welcome back" in res.get("prompt")
        print("-> IVR Call state machine flow: PASSED")

        # ----------------------------------------------------
        # TEST 3: Unverified Caller Verification
        # ----------------------------------------------------
        print("\n--- TEST 3: Unverified Caller verification ---")
        unverified_call_id = f"call-test-{uuid.uuid4().hex[:6]}"
        unverified_phone = "9988776655"
        
        # Start call
        session_unverified = ivr_manager.get_or_create_call(unverified_call_id, unverified_phone, db)
        assert session_unverified.user_id is None
        
        # 3.1: Incoming -> Consent
        res = session_unverified.advance_state("INIT")
        assert session_unverified.state == IVRState.RECORDING_CONSENT_PENDING
        
        # 3.2: Consent -> Language Selection
        res = session_unverified.advance_state("DTMF", "1")
        assert session_unverified.state == IVRState.LANGUAGE_SELECTION_PENDING
        
        # 3.3: Language Selection -> Verification Pending (Since user_id is missing)
        res = session_unverified.advance_state("DTMF", "1")
        print("State transition response:", res)
        assert session_unverified.state == IVRState.VERIFICATION_PENDING
        assert "key in your 6 digit booking reference" in res.get("prompt").lower()

        # 3.4: Verification Pending -> Active Agent
        res = session_unverified.advance_state("DTMF", booking_code)
        print("State transition response:", res)
        assert session_unverified.state == IVRState.ACTIVE_AGENT
        assert "verified" in res.get("prompt").lower()
        
        # Validate that the reference booking is stored in the session entities
        from app.conversation.manager import ConversationManager
        conv_mgr = ConversationManager()
        entities = conv_mgr.get_session(session_unverified.session_id).entities
        print("Session entities stored:", entities)
        assert entities.get("booking_code") == booking_code
        print("-> Unverified Caller Verification: PASSED")

        # Cleanup test records
        print("\nCleaning up database records...")
        db.delete(booking)
        # Delete any trips on this route (including the rescheduled one)
        db.query(Trip).filter(Trip.route_id == route.id).delete()
        db.commit()

        # Now delete bus, route, and user
        db.delete(bus)
        db.delete(route)
        db.delete(user)
        db.commit()
        print("Cleanup completed.")

        print("\nALL IVR TELEPHONY AND RESCHEDULING UPGRADE TESTS PASSED SUCCESSFULLY! [SUCCESS]")
        db.close()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    from datetime import timedelta
    success = run_tests()
    if not success:
        sys.exit(1)
