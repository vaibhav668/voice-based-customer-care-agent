import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Ensure backend directory is on sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.database.models.user import User
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.trip import Trip, TripStatus
from app.database.models.booking import Booking, BookingStatus, PaymentStatus

def seed_jayam_bookings():
    db = SessionLocal()
    print("Connecting to database...")
    
    try:
        # 1. Locate the existing user Jayam (9392273983)
        phone_number = "9392273983"
        user = db.query(User).filter_by(phone=phone_number).first()
        if not user:
            print(f"Error: User with phone number {phone_number} not found. Please register the user first.")
            return

        print(f"Located User: {user.full_name} ({user.phone}), ID: {user.id}")

        # ----------------------------------------------------
        # Flight Booking Seed
        # ----------------------------------------------------
        route_f = db.query(Route).filter_by(source_city="Delhi", destination_city="Chennai").first()
        if not route_f:
            route_f = Route(
                id=uuid.uuid4(),
                source_city="Delhi",
                destination_city="Chennai",
                distance_km=1746.0,
                estimated_duration_minutes=160,
            )
            db.add(route_f)
            db.commit()
            db.refresh(route_f)
            print(f"Created Flight Route: Delhi -> Chennai, ID: {route_f.id}")

        bus_f = db.query(Bus).filter_by(bus_number="6E-2134").first()
        if not bus_f:
            bus_f = Bus(
                id=uuid.uuid4(),
                bus_number="6E-2134",
                bus_name="IndiGo Flight 6E-2134",
                registration_number="VT-IDG",
                bus_type=BusType.AC_SEATER,
                capacity=180,
            )
            db.add(bus_f)
            db.commit()
            db.refresh(bus_f)
            print(f"Created Flight: {bus_f.bus_name} ({bus_f.bus_number})")

        dep_f = datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc)
        arr_f = dep_f + timedelta(minutes=160)
        trip_f = db.query(Trip).filter_by(route_id=route_f.id, bus_id=bus_f.id, departure_time=dep_f).first()
        if not trip_f:
            trip_f = Trip(
                id=uuid.uuid4(),
                route_id=route_f.id,
                bus_id=bus_f.id,
                departure_time=dep_f,
                arrival_time=arr_f,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=179,
            )
            db.add(trip_f)
            db.commit()
            db.refresh(trip_f)
            print(f"Created Flight Trip: {dep_f}")

        booking_code_f = "BK-939227"
        booking_f = db.query(Booking).filter_by(booking_code=booking_code_f).first()
        if not booking_f:
            booking_f = Booking(
                id=uuid.uuid4(),
                booking_code=booking_code_f,
                user_id=user.id,
                trip_id=trip_f.id,
                seat_number="12A",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
                booking_date=datetime.now(timezone.utc),
            )
            db.add(booking_f)
            db.commit()
            print(f"Seeded Flight Booking: {booking_code_f}")

        # ----------------------------------------------------
        # Bus Booking Seed
        # ----------------------------------------------------
        route_b = db.query(Route).filter_by(source_city="Delhi", destination_city="Jaipur").first()
        if not route_b:
            route_b = Route(
                id=uuid.uuid4(),
                source_city="Delhi",
                destination_city="Jaipur",
                distance_km=280.0,
                estimated_duration_minutes=315,
            )
            db.add(route_b)
            db.commit()
            db.refresh(route_b)
            print(f"Created Bus Route: Delhi -> Jaipur, ID: {route_b.id}")

        bus_b = db.query(Bus).filter_by(bus_number="AP39AB1001").first()
        if not bus_b:
            bus_b = Bus(
                id=uuid.uuid4(),
                bus_number="AP39AB1001",
                bus_name="Volvo Multi Axle AC Sleeper",
                registration_number="AP39BUS1001",
                bus_type=BusType.AC_SLEEPER,
                capacity=36,
            )
            db.add(bus_b)
            db.commit()
            db.refresh(bus_b)
            print(f"Created Bus: {bus_b.bus_name} ({bus_b.bus_number})")

        dep_b = datetime(2026, 8, 16, 22, 0, tzinfo=timezone.utc)
        arr_b = dep_b + timedelta(minutes=315)
        trip_b = db.query(Trip).filter_by(route_id=route_b.id, bus_id=bus_b.id, departure_time=dep_b).first()
        if not trip_b:
            trip_b = Trip(
                id=uuid.uuid4(),
                route_id=route_b.id,
                bus_id=bus_b.id,
                departure_time=dep_b,
                arrival_time=arr_b,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35,
            )
            db.add(trip_b)
            db.commit()
            db.refresh(trip_b)
            print(f"Created Bus Trip: {dep_b}")

        booking_code_b = "BK-939228"
        booking_b = db.query(Booking).filter_by(booking_code=booking_code_b).first()
        if not booking_b:
            booking_b = Booking(
                id=uuid.uuid4(),
                booking_code=booking_code_b,
                user_id=user.id,
                trip_id=trip_b.id,
                seat_number="15",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
                booking_date=datetime.now(timezone.utc),
            )
            db.add(booking_b)
            db.commit()
            print(f"Seeded Bus Booking: {booking_code_b}")

        print("All Jayam bookings successfully seeded!")

    except Exception as e:
        db.rollback()
        print(f"Failed to seed booking: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_jayam_bookings()
