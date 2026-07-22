import os
import sys
import uuid
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.user import User, UserRole
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.trip import Trip, TripStatus
from app.database.models.booking import Booking, BookingStatus, PaymentStatus
from app.auth.security import hash_password
from app.database.base import Base

def seed_for_engine(engine, db_name):
    print(f"\n--- Seeding Database ({db_name}) ---")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        phone = "6300076108"
        full_name = "Yaseen"
        email = "yaseen@example.com"
        
        # 1. User
        user = db.query(User).filter_by(phone=phone).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                full_name_legacy=full_name,
                email=email,
                phone=phone,
                password_hash=hash_password("yaseen123"),
                role=UserRole.CUSTOMER,
                is_active=True,
                is_verified=True,
                preferred_language="en",
            )
            user.full_name = full_name
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created User: {full_name} ({phone}), ID: {user.id}")
        else:
            print(f"User already exists: {full_name} ({phone}), ID: {user.id}")

        # 2. Route: Delhi -> Goa
        route = db.query(Route).filter_by(source_city="Delhi", destination_city="Goa").first()
        if not route:
            route = Route(
                id=uuid.uuid4(),
                source_city="Delhi",
                destination_city="Goa",
                distance_km=1875.0,
                estimated_duration_minutes=1500,
            )
            db.add(route)
            db.commit()
            db.refresh(route)
            print(f"Created Route: Delhi -> Goa, ID: {route.id}")
        else:
            print(f"Route Delhi -> Goa exists, ID: {route.id}")

        # 3. Bus
        bus_num = "DL01GOA"
        bus = db.query(Bus).filter_by(bus_number=bus_num).first()
        if not bus:
            bus = Bus(
                id=uuid.uuid4(),
                bus_number=bus_num,
                bus_name="Volvo AC Multi-Axle Sleeper (Delhi to Goa)",
                registration_number="DL01GA6300",
                bus_type=BusType.AC_SLEEPER,
                capacity=36,
            )
            db.add(bus)
            db.commit()
            db.refresh(bus)
            print(f"Created Bus: {bus_num}, ID: {bus.id}")
        else:
            print(f"Bus exists: {bus_num}, ID: {bus.id}")

        # 4. Trip
        now = datetime.now()
        dep_time = now.replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=2)
        arr_time = dep_time + timedelta(hours=25)

        trip = db.query(Trip).filter_by(route_id=route.id, bus_id=bus.id).first()
        if not trip:
            trip = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=bus.id,
                departure_time=dep_time,
                arrival_time=arr_time,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35,
            )
            db.add(trip)
            db.commit()
            db.refresh(trip)
            print(f"Created Trip: {dep_time} -> {arr_time}, ID: {trip.id}")
        else:
            print(f"Trip exists, ID: {trip.id}")

        # 5. Booking
        booking_code = "BK-630007"
        booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if not booking:
            booking = Booking(
                id=uuid.uuid4(),
                booking_code=booking_code,
                user_id=user.id,
                trip_id=trip.id,
                seat_number="A01",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
                booking_date=datetime.now(),
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            print(f"Created Booking: {booking_code} for user {user.phone} ({full_name}) from Delhi to Goa!")
        else:
            print(f"Booking already exists: {booking_code}")

    finally:
        db.close()

def main():
    # 1. Seed SQLite Database
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "supportai.db")
    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    seed_for_engine(sqlite_engine, "SQLite supportai.db")

    # 2. Seed PostgreSQL Database if available
    postgres_url = "postgresql://postgres:postgres@localhost:5432/supportai"
    try:
        pg_engine = create_engine(postgres_url, connect_args={"connect_timeout": 3})
        seed_for_engine(pg_engine, "PostgreSQL supportai")
    except Exception as e:
        print(f"\nPostgreSQL seeding skipped/failed: {e}")

if __name__ == "__main__":
    main()
