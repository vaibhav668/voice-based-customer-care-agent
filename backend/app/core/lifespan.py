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
    from datetime import datetime, timedelta

    db = SessionLocal()
    try:
        existing = db.query(Booking).filter(Booking.booking_code == "BK-100001").first()
        if existing:
            return

        logger.info("🌱 Seeding initial database records (BK-100001, routes, buses, trips)...")

        user = User(
            full_name="Sample Customer",
            email="customer@example.com",
            phone="9876543210",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        route = Route(
            source_city="Delhi",
            destination_city="Mumbai",
            distance_km=1400,
            estimated_duration_minutes=1200,
        )
        db.add(route)
        db.commit()
        db.refresh(route)

        bus = Bus(
            bus_number="DL01BUS1001",
            bus_name="Volvo Multi Axle AC Sleeper",
            registration_number="DL01REG1001",
            bus_type=BusType.AC_SLEEPER,
            capacity=36,
        )
        db.add(bus)
        db.commit()
        db.refresh(bus)

        departure = datetime.now() + timedelta(hours=4)
        arrival = departure + timedelta(hours=18)

        trip = Trip(
            route_id=route.id,
            bus_id=bus.id,
            departure_time=departure,
            arrival_time=arrival,
            status=TripStatus.SCHEDULED,
            delay_minutes=0,
            available_seats=35,
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)

        booking = Booking(
            booking_code="BK-100001",
            user_id=user.id,
            trip_id=trip.id,
            seat_number="A12",
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID,
        )
        db.add(booking)
        db.commit()
        logger.info("✅ Database seeded with initial booking BK-100001.")
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

        auto_seed_database()

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
                    conn.execute(text("ALTER TABLE trips ADD COLUMN updated_eta DATETIME"))
    except Exception as e:
        logger.warning(f"Database table/column sync warning: {e}")
    yield
    logger.info("🛑 SupportAI Backend Stopped")