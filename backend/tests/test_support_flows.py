import os
import sys
import uuid
from datetime import datetime, date

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.database.models.user import User, UserRole
from app.database.models.booking import Booking
from app.database.models.conversation import Conversation
from app.database.models.campaign import Campaign
from app.database.models.call_review import CallReview
from app.ai.understanding.node import understand
from app.ai.intent.schemas import Intent
from app.services.chat_service import ChatService
from app.exceptions.common import NotFoundException

def run_tests():
    from app.database.session import engine
    from app.database.base import Base
    import app.database.models
    from sqlalchemy import inspect, text
    
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "users" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("users")]
            if "name_encrypted" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN name_encrypted VARCHAR(255)"))
            if "full_name" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"))

    Base.metadata.create_all(bind=engine)

    # Run alter migrations as well
    from migrate import run_migrations
    run_migrations()

    # Seed the database
    from app.core.lifespan import auto_seed_database
    auto_seed_database()

    db = SessionLocal()
    print("==================================================")
    print("STARTING UPGRADE TRAVEL BOOKING SUPPORT FLOW TESTS")
    print("==================================================")

    try:
        # 0. Setup and Seed Test Data
        # Retrieve primary test user vaibhav@gmail.com
        user = db.query(User).filter_by(email="vaibhav@gmail.com").first()
        if not user:
            print("Seeding test user...")
            user = User(
                id=uuid.uuid4(),
                full_name="Vaibhav Pokhriyal",
                email="vaibhav@gmail.com",
                phone="9568987360",
                password_hash="fakehash",
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Retrieve/create another user
        other_user = db.query(User).filter_by(email="other@example.com").first()
        if not other_user:
            other_user = User(
                id=uuid.uuid4(),
                full_name="Other User",
                email="other@example.com",
                phone="9998887999",
                password_hash="fakehash",
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
            )
            db.add(other_user)
            db.commit()
            db.refresh(other_user)

        # Retrieve/create booking BK-1234
        booking = db.query(Booking).filter_by(booking_code="BK-1234").first()
        if not booking:
            print("No BK-1234 booking found. Please seed DB first.")
            return False

        # Ensure BK-1234 belongs to vaibhav
        booking.user_id = user.id
        db.commit()

        # Ensure BK-1234's trip route is populated with source="Delhi" and destination="Jaipur"
        if booking.trip:
            if not booking.trip.route:
                from app.database.models.route import Route
                route = Route(source_city="Delhi", destination_city="Jaipur", distance_km=280, estimated_duration_minutes=300)
                db.add(route)
                db.commit()
                booking.trip.route_id = route.id
                db.commit()
            else:
                booking.trip.route.source_city = "Delhi"
                booking.trip.route.destination_city = "Jaipur"
                db.commit()

        # Create test campaign
        campaign = db.query(Campaign).filter_by(name="Test July Campaign").first()
        if not campaign:
            campaign = Campaign(
                id=uuid.uuid4(),
                name="Test July Campaign",
                type="OUTBOUND",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

        # Create a conversation session
        conv_session_id = f"test-sess-{uuid.uuid4().hex[:6]}"

        # --------------------------------------------------
        # 1. NLU Intent Classification Tests
        # --------------------------------------------------
        print("\n--- 1. Testing NLU Intent Classification ---")
        
        # Test ESCALATE_TO_HUMAN
        res1 = understand("talk to a human support agent please")
        print(f"Input: 'talk to a human support agent please' -> Intent: {res1.intent}")
        assert res1.intent == Intent.ESCALATE_TO_HUMAN

        # Test PROFILE_STATUS
        res2 = understand("show my personal profile details")
        print(f"Input: 'show my personal profile details' -> Intent: {res2.intent}")
        assert res2.intent == Intent.PROFILE_STATUS

        # Test LANGUAGE_CHANGE
        res3 = understand("change my preferred language to Hindi")
        print(f"Input: 'change my preferred language to Hindi' -> Intent: {res3.intent} | Lang: {res3.language}")
        assert res3.intent == Intent.LANGUAGE_CHANGE
        assert res3.language == "hi"

        print("NLU Classification checks passed!")

        # --------------------------------------------------
        # 2. Strict Scoped Identity Verification checks
        # --------------------------------------------------
        print("\n--- 2. Testing Scoped Security Verification Boundary ---")
        chat_service = ChatService(db=db)

        # Scenario A: Anonymous caller queries BK-1234 WITHOUT phone validation
        # Expecting details query to fail/throw exception, or return unauthorized response
        from app.schemas.chat import ChatRequest
        print("Scenario A: Guest queries private booking BK-1234 without verification...")
        resp_guest = chat_service.process(
            request=ChatRequest(session_id=conv_session_id, message="What is my booking status? BK-1234"),
            user_id=None,
            channel="VOICE"
        )
        print(f"-> Response: {resp_guest.get('response')}")
        assert "unable to find" in resp_guest.get("response").lower() or "permission" in resp_guest.get("response").lower() or "verify" in resp_guest.get("response").lower()
        # Verify details were NOT leaked
        assert "Delhi" not in resp_guest.get("response")
        assert "Jaipur" not in resp_guest.get("response")
        print("-> SUCCESS: Lookup successfully blocked and no leak occurred.")

        # Scenario B: Guest queries BK-1234 with matching phone
        owner_phone = user.phone or "9568987360"
        print(f"Scenario B: Guest queries BK-1234 providing registered phone number {owner_phone}...")
        # First send the phone number to save in session entities
        chat_service.process(
            request=ChatRequest(session_id=conv_session_id, message=f"My phone number is {owner_phone}"),
            user_id=None,
            channel="VOICE"
        )
        # Then check booking
        resp = chat_service.process(
            request=ChatRequest(session_id=conv_session_id, message="What is my booking status? BK-1234"),
            user_id=None,
            channel="VOICE"
        )
        print(f"-> Response: {resp.get('response')[:60]}...")
        assert "Delhi" in resp.get("response") or "Jaipur" in resp.get("response") or "confirmed" in resp.get("response").lower()
        print("-> SUCCESS: Private booking details accessed after matching phone verification!")

        # Scenario C: Authenticated Owner User (vaibhav) queries BK-1234
        print("Scenario C: Authenticated owner user queries booking status...")
        new_sess = f"test-sess-{uuid.uuid4().hex[:6]}"
        resp_owner = chat_service.process(
            request=ChatRequest(session_id=new_sess, message="What is my booking status? BK-1234"),
            user_id=str(user.id),
            channel="CHAT"
        )
        print(f"-> Response: {resp_owner.get('response')[:60]}...")
        assert "Delhi" in resp_owner.get("response") or "Jaipur" in resp_owner.get("response") or "confirmed" in resp_owner.get("response").lower()
        print("-> SUCCESS: Owner access permitted.")

        # Scenario D: Authenticated Other User queries BK-1234
        print("Scenario D: Another user attempts to query BK-1234...")
        resp_other = chat_service.process(
            request=ChatRequest(session_id=new_sess, message="What is my booking status? BK-1234"),
            user_id=str(other_user.id),
            channel="CHAT"
        )
        print(f"-> Response: {resp_other.get('response')}")
        assert "unable to find" in resp_other.get("response").lower() or "permission" in resp_other.get("response").lower() or "verify" in resp_other.get("response").lower()
        # Verify details were NOT leaked
        assert "Delhi" not in resp_other.get("response")
        assert "Jaipur" not in resp_other.get("response")
        print("-> SUCCESS: Lookup successfully blocked for unauthorized user.")

        # --------------------------------------------------
        # 3. New Intent Tools Checks (Profile, Language, Escalate)
        # --------------------------------------------------
        print("\n--- 3. Testing New Support Intent Tools ---")

        # Test Profile Retrieval
        profile_sess = f"test-sess-{uuid.uuid4().hex[:6]}"
        resp_profile = chat_service.process(
            request=ChatRequest(session_id=profile_sess, message="Show my profile"),
            user_id=str(user.id),
            channel="CHAT"
        )
        print(f"Profile Response: {resp_profile.get('response')}")
        assert "Vaibhav" in resp_profile.get("response")
        assert (user.phone or "9568987360") in resp_profile.get("response")

        # Test Language Changing
        lang_sess = f"test-sess-{uuid.uuid4().hex[:6]}"
        resp_lang = chat_service.process(
            request=ChatRequest(session_id=lang_sess, message="Change language to Hindi"),
            user_id=str(user.id),
            channel="CHAT"
        )
        print(f"Language Response: {resp_lang.get('response')}")
        # Fetch conversation from DB to verify language has updated to 'hi'
        db_conv = db.query(Conversation).filter_by(session_id=lang_sess).first()
        assert db_conv.language == "hi"
        print("-> SUCCESS: Language preference updated in DB!")

        # Test Escalation to Human
        escalate_sess = f"test-sess-{uuid.uuid4().hex[:6]}"
        resp_esc = chat_service.process(
            request=ChatRequest(session_id=escalate_sess, message="talk to a human"),
            user_id=str(user.id),
            channel="VOICE"
        )
        print(f"Escalate Response: {resp_esc.get('response')}")
        # Fetch conversation from DB to verify resolution_status has updated to 'escalated'
        db_conv_esc = db.query(Conversation).filter_by(session_id=escalate_sess).first()
        assert db_conv_esc.resolution_status == "escalated"
        print("-> SUCCESS: Resolution status updated to 'escalated' in DB!")

        # --------------------------------------------------
        # 4. Intent Override for Booking-Specific Queries
        # --------------------------------------------------
        print("\n--- 4. Testing Intent Override for Booking-Specific Queries ---")
        override_sess = f"test-sess-{uuid.uuid4().hex[:6]}"
        
        # Hydrate the session with a verified booking code BK-1234 (must first verify ownership using registered phone number)
        owner_phone = user.phone or "9568987360"
        chat_service.process(
            request=ChatRequest(session_id=override_sess, message=f"My phone number is {owner_phone}"),
            user_id=None,
            channel="VOICE"
        )
        chat_service.process(
            request=ChatRequest(session_id=override_sess, message="Check booking BK-1234"),
            user_id=None,
            channel="VOICE"
        )
        
        # Now ask: "arrival time" (which normally classifies as Intent.FAQ)
        resp_arrival = chat_service.process(
            request=ChatRequest(session_id=override_sess, message="arrival time"),
            user_id=None,
            channel="VOICE"
        )
        print(f"Arrival Time Query Response: {resp_arrival.get('response')}")
        response_text = resp_arrival.get("response").lower()
        assert "arrival" in response_text or "arrive" in response_text or "23:45" in response_text or "11:45" in response_text or "pm" in response_text
        
        # Now ask: "I want to know my destination" (which normally classifies as Intent.LIST_BOOKINGS or Intent.GENERAL)
        resp_dest = chat_service.process(
            request=ChatRequest(session_id=override_sess, message="I want to know my destination"),
            user_id=None,
            channel="VOICE"
        )
        print(f"Destination Query Response: {resp_dest.get('response')}")
        assert "jaipur" in resp_dest.get("response").lower()
        
        # Verify the DB message has intent == BOOKING_STATUS
        db_conv_override = db.query(Conversation).filter_by(session_id=override_sess).first()
        assert db_conv_override.current_intent == "Intent.BOOKING_STATUS" or db_conv_override.current_intent == "BOOKING_STATUS"
        print("-> SUCCESS: Intent override for booking-specific queries verified successfully!")

        print("\n==================================================")
        print("ALL TRAVEL BOOKING PLATFORM SYSTEM UPGRADE TESTS PASSED!")
        print("==================================================")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
