from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.base import Base
import app.database.models  # Ensures all ORM models are registered with Base.metadata


def ensure_admin_roles():
    """Guarantees that all designated admin accounts have the ADMIN role.
    This runs separately from seeding so it always executes even if DB is pre-seeded."""
    from app.database.session import SessionLocal
    from app.database.models.user import User, UserRole

    db = SessionLocal()
    try:
        # List of emails that MUST be ADMIN
        admin_emails = ["admin@gmail.com", "admin@example.com"]
        for email in admin_emails:
            user = db.query(User).filter_by(email=email).first()
            if user and user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                db.commit()
                logger.info(f"Enforced ADMIN role on {email}")
    except Exception as e:
        logger.warning(f"ensure_admin_roles warning: {e}")
        db.rollback()
    finally:
        db.close()


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
        # IMPORTANT: Use phone numbers that don't conflict with existing DB entries.
        # These are the authoritative phone numbers for seeded accounts.
        test_users_data = [
            {"email": "vaibhav@gmail.com", "name": "Vaibhav Pokhriyal", "pw": "vaibhav123", "phone": "8266894170", "role": UserRole.CUSTOMER},
            {"email": "admin@gmail.com", "name": "Admin User", "pw": "admin123", "phone": "9568987369", "role": UserRole.ADMIN},
            {"email": "mnc@gmail.com", "name": "mnc", "pw": "mnc123", "phone": "9568987361", "role": UserRole.CUSTOMER},
            {"email": "vpokhriyal35@gmail.com", "name": "vaibhav", "pw": "vpokhriyal35123", "phone": "9568987362", "role": UserRole.CUSTOMER},
            {"email": "vaibhav100@example.com", "name": "Vaibhav", "pw": "vaibhav100123", "phone": "9568987363", "role": UserRole.CUSTOMER},
            {"email": "user@example.com", "name": "string", "pw": "user123", "phone": "9568987364", "role": UserRole.CUSTOMER},
            {"email": "demo@example.com", "name": "Demo User", "pw": "password123", "phone": "9876543999", "role": UserRole.CUSTOMER},
            {"email": "other@example.com", "name": "Other User", "pw": "password123", "phone": "8178265989", "role": UserRole.CUSTOMER},
            {"email": "admin@example.com", "name": "System Admin", "pw": "admin123", "phone": "9990001112", "role": UserRole.ADMIN},
        ]

        users_dict = {}
        for ud in test_users_data:
            user = db.query(User).filter_by(email=ud["email"]).first()
            hashed_pw = hash_password(ud["pw"])
            role_val = ud.get("role", UserRole.CUSTOMER)
            if not user:
                # Check if phone already taken by another user before creating
                existing_phone = db.query(User).filter_by(phone=ud["phone"]).first()
                if existing_phone:
                    logger.warning(f"Phone {ud['phone']} already in use by {existing_phone.email}, skipping create for {ud['email']}")
                    users_dict[ud["email"]] = existing_phone
                    continue
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
                # Always sync password hash, phone number, and role to the authoritative values
                user.password_hash = hashed_pw
                user.role = role_val
                if user.phone != ud["phone"]:
                    existing_phone = db.query(User).filter_by(phone=ud["phone"]).first()
                    if existing_phone and existing_phone.id != user.id:
                        logger.warning(f"Phone {ud['phone']} already in use by {existing_phone.email}, cannot sync phone for {user.email}")
                    else:
                        user.phone = ud["phone"]
                db.commit()
                db.refresh(user)
            users_dict[ud["email"]] = user

        # Primary user for booking scenarios — use whichever vaibhav user exists
        user = users_dict.get("vaibhav@gmail.com") or db.query(User).filter(User.role == UserRole.CUSTOMER).first()
        other_user = users_dict.get("other@example.com") or user

        # Ensure Yaseen user (6300076108) and booking BK-630007 (Delhi -> Goa) exist
        yaseen = db.query(User).filter((User.phone == "6300076108") | (User.email == "yaseen@example.com")).first()
        if not yaseen:
            yaseen = User(
                id=uuid.uuid4(),
                full_name="Yaseen",
                email="yaseen@example.com",
                phone="6300076108",
                password_hash=hash_password("yaseen123"),
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
                preferred_language="en",
            )
            db.add(yaseen)
            db.commit()
            db.refresh(yaseen)

        bk_yaseen = db.query(Booking).filter(Booking.booking_code == "BK-630007").first()
        if not bk_yaseen:
            route_goa = db.query(Route).filter_by(source_city="Delhi", destination_city="Goa").first()
            if not route_goa:
                route_goa = Route(
                    id=uuid.uuid4(),
                    source_city="Delhi",
                    destination_city="Goa",
                    distance_km=1875,
                    estimated_duration_minutes=1500,
                )
                db.add(route_goa)
                db.commit()
                db.refresh(route_goa)

            bus_goa = db.query(Bus).filter_by(bus_number="DL01GOA").first()
            if not bus_goa:
                bus_goa = Bus(
                    id=uuid.uuid4(),
                    bus_number="DL01GOA",
                    bus_name="Volvo AC Multi-Axle Sleeper (Delhi to Goa)",
                    registration_number="DL01GA6300",
                    bus_type=BusType.AC_SLEEPER,
                    capacity=36,
                )
                db.add(bus_goa)
                db.commit()
                db.refresh(bus_goa)

            now_time = datetime.now()
            dep_goa = now_time.replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=2)
            arr_goa = dep_goa + timedelta(hours=25)
            trip_goa = Trip(
                id=uuid.uuid4(),
                route_id=route_goa.id,
                bus_id=bus_goa.id,
                departure_time=dep_goa,
                arrival_time=arr_goa,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35,
            )
            db.add(trip_goa)
            db.commit()
            db.refresh(trip_goa)

            bk_yaseen = Booking(
                booking_code="BK-630007",
                user_id=yaseen.id,
                trip_id=trip_goa.id,
                seat_number="A01",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
            )
            db.add(bk_yaseen)
            db.commit()
            logger.info("Seeded Yaseen booking BK-630007 (Delhi -> Goa)")
        elif bk_yaseen.user_id != yaseen.id:
            bk_yaseen.user_id = yaseen.id
            db.commit()
            logger.info(f"Re-assigned BK-630007 to Yaseen user_id {yaseen.id}")

        # Check if already seeded to avoid duplicates — note: role sync above already ran
        existing = db.query(Booking).filter(Booking.booking_code == "BK-1234").first()
        if existing:
            logger.info("Database already seeded, skipping booking/route creation.")
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

        # Ensure all existing bookings are linked to a test user if user_id is null
        null_user_bookings = db.query(Booking).filter(Booking.user_id == None).all()
        if null_user_bookings:
            default_user = db.query(User).filter_by(role=UserRole.CUSTOMER).first()
            if not default_user:
                default_user = db.query(User).first()
            if default_user:
                for bk in null_user_bookings:
                    bk.user_id = default_user.id
                db.commit()
                logger.info(f"Synced {len(null_user_bookings)} bookings to user {default_user.email}")

        logger.info("✅ Database seeded with all customer support test scenarios.")
    except Exception as e:
        logger.warning(f"Auto-seed warning: {e}")
        db.rollback()
    finally:
        db.close()


def fix_foreign_keys_referring_to_users_old():
    """Finds any foreign key constraints pointing to 'users_old' table 
    (often caused by table rename migrations in PostgreSQL) and drops/recreates 
    them to point to the correct 'users' table."""
    from app.database.session import engine
    from sqlalchemy import text
    
    if engine.dialect.name != "postgresql":
        return

    try:
        with engine.begin() as conn:
            # Query constraints pointing to users_old via system catalogs
            query = text("""
                SELECT c.conname, t.relname AS tablename, a.attname AS colname
                FROM pg_constraint c
                JOIN pg_class r ON c.confrelid = r.oid
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_attribute a ON a.attnum = c.conkey[1] AND a.attrelid = t.oid
                WHERE r.relname = 'users_old'
            """)
            results = conn.execute(query).fetchall()
            
            if not results:
                logger.info("No foreign key constraints referencing users_old found.")
                return
                
            for conname, tablename, colname in results:
                logger.info(f"Found invalid foreign key constraint '{conname}' on table '{tablename}' column '{colname}' referencing 'users_old'!")
                
                try:
                    # 1. Clean up invalid data that would break constraint validation
                    if tablename in ("conversations", "bookings"):
                        logger.info(f"Cleaning up orphan {colname} in {tablename} by setting to NULL...")
                        conn.execute(text(
                            f'UPDATE "{tablename}" SET "{colname}" = NULL '
                            f'WHERE "{colname}" IS NOT NULL AND "{colname}" NOT IN (SELECT "id" FROM "users")'
                        ))
                    elif tablename == "call_reviews":
                        logger.info(f"Deleting orphan rows in call_reviews referring to non-existent users...")
                        conn.execute(text(
                            f'DELETE FROM "call_reviews" WHERE "{colname}" NOT IN (SELECT "id" FROM "users")'
                        ))
                    
                    # 2. Drop the old constraint
                    logger.info(f"Dropping constraint '{conname}' on table '{tablename}'...")
                    conn.execute(text(f'ALTER TABLE "{tablename}" DROP CONSTRAINT "{conname}"'))
                    
                    # 3. Add the corrected constraint referencing 'users'
                    logger.info(f"Adding constraint '{conname}' pointing to 'users' table...")
                    conn.execute(text(
                        f'ALTER TABLE "{tablename}" ADD CONSTRAINT "{conname}" '
                        f'FOREIGN KEY ("{colname}") REFERENCES "users"("id")'
                    ))
                    logger.info(f"Successfully repaired constraint '{conname}'!")
                except Exception as ex:
                    logger.warning(f"Error repairing constraint '{conname}': {ex}")
                    
    except Exception as e:
        logger.warning(f"Error inspecting/repairing pg foreign keys referencing users_old: {e}")


@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 SupportAI Backend Started")
    try:
        # Check and resolve any PostgreSQL foreign key constraints pointing to users_old
        fix_foreign_keys_referring_to_users_old()

        # Check if users table needs migration (adding name_encrypted column)
        with engine.begin() as conn:
            inspector = inspect(conn)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "name_encrypted" not in columns:
                    logger.info("Migrating database: Adding name_encrypted column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN name_encrypted VARCHAR(255)"))
                    
                    if "full_name" in columns:
                        from app.database.models.user import encrypt_field
                        res = conn.execute(text("SELECT id, full_name FROM users")).fetchall()
                        for row in res:
                            encrypted_name = encrypt_field(row[1])
                            conn.execute(
                                text("UPDATE users SET name_encrypted = :enc WHERE id = :id"),
                                {"enc": encrypted_name, "id": row[0]}
                            )
                        logger.info("Encrypted existing users full_name values.")

        # Create all database tables automatically if missing
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")

        # Create performance-enhancing indexes
        with engine.begin() as conn:
            logger.info("Creating performance-enhancing database indexes...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ivr_sessions_session_id ON ivr_sessions (session_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bookings_trip_id ON bookings (trip_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_campaign_id ON conversations (campaign_id)"))

        # Check and ensure legacy full_name column exists for compatibility
        with engine.begin() as conn:
            inspector = inspect(conn)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "full_name" not in columns:
                    logger.info("Migrating database: Adding full_name column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"))

        try:
            from migrate import run_migrations
            run_migrations()
        except Exception as e:
            logger.warning(f"Auto-migration warning: {e}")

        auto_seed_database()
        ensure_admin_roles()  # Always enforce admin roles after seed (handles pre-seeded DBs)

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
                
                if "name_encrypted" not in columns:
                    logger.info("Adding name_encrypted column and migrating existing data...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN name_encrypted VARCHAR(255)"))
                    # Migrate data from full_name to name_encrypted by encrypting it
                    if "full_name" in columns:
                        from app.database.models.user import encrypt_field
                        res = conn.execute(text("SELECT id, full_name FROM users")).fetchall()
                        for row in res:
                            encrypted = encrypt_field(row[1])
                            conn.execute(
                                text("UPDATE users SET name_encrypted = :enc WHERE id = :id"),
                                {"enc": encrypted, "id": row[0]}
                            )

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