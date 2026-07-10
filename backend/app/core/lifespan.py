from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.base import Base
import app.database.models  # Ensures all ORM models are registered with Base.metadata


def auto_seed_database():
    from app.database.session import SessionLocal
    from app.database.models.booking import Booking, BookingStatus, PaymentStatus
    from app.database.models.user import User, UserRole
    from app.database.models.route import Route
    from app.database.models.bus import Bus, BusType
    from app.database.models.trip import Trip, TripStatus
    from app.auth.security import hash_password
    from datetime import datetime, timedelta
    import uuid

    db = SessionLocal()
    try:
        # 1. Create and verify all test users
        test_users_data = [
            {"email": "vaibhav@gmail.com", "name": "Vaibhav Pokhriyal", "pw": "vaibhav123", "phone": "9568987360", "role": UserRole.CUSTOMER},
            {"email": "admin@gmail.com", "name": "admin", "pw": "admin123", "phone": "9568987369", "role": UserRole.CUSTOMER},
            {"email": "mnc@gmail.com", "name": "mnc", "pw": "mnc123", "phone": "9568987361", "role": UserRole.CUSTOMER},
            {"email": "vpokhriyal35@gmail.com", "name": "vaibhav", "pw": "vpokhriyal35123", "phone": "9568987362", "role": UserRole.CUSTOMER},
            {"email": "vaibhav100@example.com", "name": "Vaibhav", "pw": "vaibhav100123", "phone": "9568987363", "role": UserRole.CUSTOMER},
            {"email": "user@example.com", "name": "string", "pw": "user123", "phone": "9568987364", "role": UserRole.CUSTOMER},
            {"email": "demo@example.com", "name": "Demo User", "pw": "password123", "phone": "9876543999", "role": UserRole.CUSTOMER},
            {"email": "other@example.com", "name": "Other User", "pw": "password123", "phone": "9998887999", "role": UserRole.CUSTOMER},
            {"email": "admin@example.com", "name": "System Admin", "pw": "admin123", "phone": "9990001112", "role": UserRole.ADMIN},
        ]

        users_dict = {}
        for ud in test_users_data:
            user = db.query(User).filter_by(email=ud["email"]).first()
            hashed_pw = hash_password(ud["pw"])
            role_val = ud.get("role", UserRole.CUSTOMER)
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    full_name=ud["name"],
                    email=ud["email"],
                    phone=ud["phone"],
                    password_hash=hashed_pw,
                    role=role_val,
                    is_active=True,
                    is_verified=True,
                    preferred_language="en",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created test user: {ud['email']}")
            else:
                # Ensure the password hash and role are correctly synced/reset to the known value
                user.password_hash = hashed_pw
                user.role = role_val
                db.commit()
                db.refresh(user)
            users_dict[ud["email"]] = user

        user = users_dict["vaibhav@gmail.com"]  # Primary user for booking scenarios
        other_user = users_dict["other@example.com"]

        # Check if already seeded to avoid duplicates
        existing = db.query(Booking).filter(Booking.booking_code == "BK-1234").first()
        if existing:
            return

        logger.info("🌱 Seeding database with customer support test scenarios (BK-1234, BK-5678, etc.)...")

        # 2. Setup routes
        route_data = [
            {"source": "Delhi", "dest": "Jaipur", "distance": 280, "duration": 315},
            {"source": "Mumbai", "dest": "Pune", "distance": 150, "duration": 270},
            {"source": "Bengaluru", "dest": "Chennai", "distance": 350, "duration": 510},
            {"source": "Hyderabad", "dest": "Vijayawada", "distance": 270, "duration": 360},
            {"source": "Dehradun", "dest": "Delhi", "distance": 250, "duration": 390},
        ]
        
        routes_dict = {}
        for rd in route_data:
            route = db.query(Route).filter_by(source_city=rd["source"], destination_city=rd["dest"]).first()
            if not route:
                route = Route(
                    id=uuid.uuid4(),
                    source_city=rd["source"],
                    destination_city=rd["dest"],
                    distance_km=rd["distance"],
                    estimated_duration_minutes=rd["duration"]
                )
                db.add(route)
                db.commit()
                db.refresh(route)
            routes_dict[f"{rd['source']}-{rd['dest']}"] = route

        buses_dict = {}
        for i in range(5):
            bus_num = f"DEMO{i}BUS"
            bus = db.query(Bus).filter_by(bus_number=bus_num).first()
            if not bus:
                bus = Bus(
                    id=uuid.uuid4(),
                    bus_number=bus_num,
                    bus_name=f"Volvo Multi Axle AC Sleeper {i}",
                    registration_number=f"DEMOREG{i}",
                    bus_type=BusType.AC_SLEEPER,
                    capacity=36
                )
                db.add(bus)
                db.commit()
                db.refresh(bus)
            buses_dict[i] = bus

        now = datetime.now()

        # BK-1234: Delhi -> Jaipur, Confirmed/Paid/On Time
        b1_code = "BK-1234"
        if not db.query(Booking).filter_by(booking_code=b1_code).first():
            route = routes_dict["Delhi-Jaipur"]
            t1 = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=buses_dict[0].id,
                departure_time=now.replace(hour=18, minute=30, second=0, microsecond=0) + timedelta(days=1),
                arrival_time=now.replace(hour=23, minute=45, second=0, microsecond=0) + timedelta(days=1),
                status=TripStatus.ON_TIME,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t1)
            db.commit()
            b1 = Booking(
                booking_code=b1_code,
                user_id=user.id,
                trip_id=t1.id,
                seat_number="A12",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b1)
            db.commit()

        # BK-5678: Mumbai -> Pune, Delayed 25 mins
        b2_code = "BK-5678"
        if not db.query(Booking).filter_by(booking_code=b2_code).first():
            route = routes_dict["Mumbai-Pune"]
            dep = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=2)
            arr = dep + timedelta(hours=4, minutes=30)
            t2 = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=buses_dict[1].id,
                departure_time=dep,
                arrival_time=arr,
                status=TripStatus.DELAYED,
                delay_minutes=25,
                delay_reason="Heavy Traffic",
                updated_eta=arr + timedelta(minutes=25),
                current_location="Approaching Lonavala",
                available_seats=35
            )
            db.add(t2)
            db.commit()
            b2 = Booking(
                booking_code=b2_code,
                user_id=user.id,
                trip_id=t2.id,
                seat_number="B07",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b2)
            db.commit()

        # BK-2468: Bengaluru -> Chennai, Cancelled/Refund Processing
        b3_code = "BK-2468"
        if not db.query(Booking).filter_by(booking_code=b3_code).first():
            route = routes_dict["Bengaluru-Chennai"]
            dep = now.replace(hour=21, minute=0, second=0, microsecond=0) + timedelta(days=5)
            arr = dep + timedelta(hours=8, minutes=30)
            t3 = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=buses_dict[2].id,
                departure_time=dep,
                arrival_time=arr,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t3)
            db.commit()
            b3 = Booking(
                booking_code=b3_code,
                user_id=user.id,
                trip_id=t3.id,
                seat_number="C15",
                booking_status=BookingStatus.CANCELLED,
                payment_status=PaymentStatus.PAID,
            )
            db.add(b3)
            db.commit()

        # BK-1357: Hyderabad -> Vijayawada, Pending/Pending
        b4_code = "BK-1357"
        if not db.query(Booking).filter_by(booking_code=b4_code).first():
            route = routes_dict["Hyderabad-Vijayawada"]
            dep = now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=3)
            arr = dep + timedelta(hours=6, minutes=0)
            t4 = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=buses_dict[3].id,
                departure_time=dep,
                arrival_time=arr,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t4)
            db.commit()
            b4 = Booking(
                booking_code=b4_code,
                user_id=user.id,
                trip_id=t4.id,
                seat_number="D09",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PENDING
            )
            db.add(b4)
            db.commit()

        # BK-9876: Dehradun -> Delhi, Confirmed/Paid/In Transit
        b5_code = "BK-9876"
        if not db.query(Booking).filter_by(booking_code=b5_code).first():
            route = routes_dict["Dehradun-Delhi"]
            dep = now.replace(hour=22, minute=0, second=0, microsecond=0) - timedelta(hours=2)
            arr = dep + timedelta(hours=6, minutes=30)
            t5 = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=buses_dict[4].id,
                departure_time=dep,
                arrival_time=arr,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                current_location="Passed Muzaffarnagar bypass, approx 120km to Delhi",
                available_seats=35
            )
            db.add(t5)
            db.commit()
            b5 = Booking(
                booking_code=b5_code,
                user_id=user.id,
                trip_id=t5.id,
                seat_number="A05",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b5)
            db.commit()

        # BK-9999: Other User booking (for cross-user security tests)
        b6_code = "BK-9999"
        if not db.query(Booking).filter_by(booking_code=b6_code).first():
            trip_obj = db.query(Trip).first()
            if trip_obj:
                b6 = Booking(
                    booking_code=b6_code,
                    user_id=other_user.id,
                    trip_id=trip_obj.id,
                    seat_number="Z99",
                    booking_status=BookingStatus.CONFIRMED,
                    payment_status=PaymentStatus.PAID
                )
                db.add(b6)
                db.commit()

        # BK-100001: Mumbai -> Pune, Cancelled
        if not db.query(Booking).filter_by(booking_code="BK-100001").first():
            t101 = Trip(
                id=uuid.uuid4(),
                route_id=routes_dict["Mumbai-Pune"].id,
                bus_id=buses_dict[1].id,
                departure_time=now + timedelta(days=4),
                arrival_time=now + timedelta(days=4, hours=4),
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t101)
            db.commit()
            b101 = Booking(
                booking_code="BK-100001",
                user_id=user.id,
                trip_id=t101.id,
                seat_number="B10",
                booking_status=BookingStatus.CANCELLED,
                payment_status=PaymentStatus.REFUNDED
            )
            db.add(b101)
            db.commit()

        # BK-100002: Delhi -> Jaipur, Confirmed
        if not db.query(Booking).filter_by(booking_code="BK-100002").first():
            t102 = Trip(
                id=uuid.uuid4(),
                route_id=routes_dict["Delhi-Jaipur"].id,
                bus_id=buses_dict[0].id,
                departure_time=now + timedelta(days=3),
                arrival_time=now + timedelta(days=3, hours=5),
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t102)
            db.commit()
            b102 = Booking(
                booking_code="BK-100002",
                user_id=user.id,
                trip_id=t102.id,
                seat_number="A04",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b102)
            db.commit()

        # BK-100003: Hyderabad -> Vijayawada, Confirmed
        if not db.query(Booking).filter_by(booking_code="BK-100003").first():
            t103 = Trip(
                id=uuid.uuid4(),
                route_id=routes_dict["Hyderabad-Vijayawada"].id,
                bus_id=buses_dict[3].id,
                departure_time=now + timedelta(days=2),
                arrival_time=now + timedelta(days=2, hours=6),
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t103)
            db.commit()
            b103 = Booking(
                booking_code="BK-100003",
                user_id=user.id,
                trip_id=t103.id,
                seat_number="D02",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b103)
            db.commit()

        # BK-100004: Dehradun -> Delhi, Confirmed
        if not db.query(Booking).filter_by(booking_code="BK-100004").first():
            t104 = Trip(
                id=uuid.uuid4(),
                route_id=routes_dict["Dehradun-Delhi"].id,
                bus_id=buses_dict[4].id,
                departure_time=now + timedelta(days=1),
                arrival_time=now + timedelta(days=1, hours=6),
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t104)
            db.commit()
            b104 = Booking(
                booking_code="BK-100004",
                user_id=user.id,
                trip_id=t104.id,
                seat_number="E11",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b104)
            db.commit()

        # BK-1010: Bengaluru -> Chennai, Confirmed
        if not db.query(Booking).filter_by(booking_code="BK-1010").first():
            t105 = Trip(
                id=uuid.uuid4(),
                route_id=routes_dict["Bengaluru-Chennai"].id,
                bus_id=buses_dict[2].id,
                departure_time=now + timedelta(days=7),
                arrival_time=now + timedelta(days=7, hours=8),
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35
            )
            db.add(t105)
            db.commit()
            b105 = Booking(
                booking_code="BK-1010",
                user_id=user.id,
                trip_id=t105.id,
                seat_number="C08",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID
            )
            db.add(b105)
            db.commit()

        # Seed Campaigns
        from app.database.models.campaign import Campaign
        from datetime import date
        existing_campaign = db.query(Campaign).filter_by(name="Outbound Support July").first()
        if not existing_campaign:
            c1 = Campaign(
                id=uuid.uuid4(),
                name="Outbound Support July",
                type="OUTBOUND",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
            )
            db.add(c1)
            db.commit()
            logger.info("Seeded default campaign: Outbound Support July")

        logger.info("✅ Database seeded with all customer support test scenarios.")
    except Exception as e:
        logger.warning(f"Auto-seed warning: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 SupportAI Backend Started")
    try:
        # Create all database tables automatically if missing
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")

        try:
            from migrate import run_migrations
            run_migrations()
        except Exception as e:
            logger.warning(f"Auto-migration warning: {e}")

        auto_seed_database()

        # Automatically ingest RAG knowledge files at startup
        try:
            from app.ai.rag.ingest import ingest_knowledge_base
            ingest_knowledge_base()
        except Exception as e:
            logger.warning(f"Failed to auto-ingest RAG knowledge base: {e}")

        with engine.begin() as conn:
            inspector = inspect(conn)
            # Users table migrations
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "preferred_language" not in columns:
                    logger.info("Adding missing preferred_language column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en'"))

            # Trips table migrations (new fields for delay/tracking)
            if "trips" in inspector.get_table_names():
                trip_cols = [c["name"] for c in inspector.get_columns("trips")]
                if "delay_reason" not in trip_cols:
                    logger.info("Adding delay_reason column to trips table...")
                    conn.execute(text("ALTER TABLE trips ADD COLUMN delay_reason VARCHAR(300)"))
                if "current_location" not in trip_cols:
                    logger.info("Adding current_location column to trips table...")
                    conn.execute(text("ALTER TABLE trips ADD COLUMN current_location VARCHAR(200)"))
                if "updated_eta" not in trip_cols:
                    logger.info("Adding updated_eta column to trips table...")
                    conn.execute(text("ALTER TABLE trips ADD COLUMN updated_eta TIMESTAMP"))
    except Exception as e:
        logger.warning(f"Database table/column sync warning: {e}")
    yield
    logger.info("🛑 SupportAI Backend Stopped")