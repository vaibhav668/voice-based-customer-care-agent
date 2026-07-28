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

def seed_jayam_flight_booking():
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

        # 2. Create Route: Delhi -> Chennai
        route = db.query(Route).filter_by(source_city="Delhi", destination_city="Chennai").first()
        if not route:
            route = Route(
                id=uuid.uuid4(),
                source_city="Delhi",
                destination_city="Chennai",
                distance_km=1746.0,
                estimated_duration_minutes=160,
            )
            db.add(route)
            db.commit()
            db.refresh(route)
            print(f"Created Route: Delhi -> Chennai, ID: {route.id}")
        else:
            print(f"Route Delhi -> Chennai already exists, ID: {route.id}")

        # 3. Create Bus (representing Airline and Flight Number)
        bus_number = "6E-2134"  # Flight Number
        bus = db.query(Bus).filter_by(bus_number=bus_number).first()
        if not bus:
            bus = Bus(
                id=uuid.uuid4(),
                bus_number=bus_number,
                bus_name="IndiGo Flight 6E-2134",
                registration_number="VT-IDG",  # Aircraft Registration
                bus_type=BusType.AC_SEATER,
                capacity=180,
            )
            db.add(bus)
            db.commit()
            db.refresh(bus)
            print(f"Created Flight (Bus): {bus.bus_name} ({bus.bus_number}), ID: {bus.id}")
        else:
            print(f"Flight (Bus) {bus_number} already exists, ID: {bus.id}")

        # 4. Create Trip (representing Flight schedule)
        # Using a realistic future travel date: 2026-08-15 10:30 AM
        departure_time = datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc)
        arrival_time = departure_time + timedelta(minutes=160) # 2 hours 40 minutes flight

        trip = db.query(Trip).filter_by(route_id=route.id, bus_id=bus.id, departure_time=departure_time).first()
        if not trip:
            trip = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=bus.id,
                departure_time=departure_time,
                arrival_time=arrival_time,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=179,
            )
            db.add(trip)
            db.commit()
            db.refresh(trip)
            print(f"Created Trip (Flight Schedule) for {departure_time}, ID: {trip.id}")
        else:
            print(f"Trip already exists, ID: {trip.id}")

        # 5. Create Booking
        # Booking code matches the system's "BK-\d{6}" format so existing logic detects it
        booking_code = "BK-939227"
        booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if not booking:
            booking = Booking(
                id=uuid.uuid4(),
                booking_code=booking_code,
                user_id=user.id,
                trip_id=trip.id,
                seat_number="12A",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
                booking_date=datetime.now(timezone.utc),
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            print(f"Successfully created Flight Booking: {booking_code} for Jayam!")
        else:
            print(f"Booking {booking_code} already exists.")

    except Exception as e:
        db.rollback()
        print(f"Failed to seed booking: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_jayam_flight_booking()
