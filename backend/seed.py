import random
import uuid
from datetime import datetime, timedelta
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal
from app.database.models.user import User, UserRole
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.trip import Trip, TripStatus
from app.database.models.booking import Booking, BookingStatus, PaymentStatus
from app.auth.security import hash_password


def seed_database():
    db = SessionLocal()
    
    print("Starting database seed process...")
    
    # 1. Create demo users (safe, idempotent)
    demo_email = "demo@example.com"
    user = db.query(User).filter_by(email=demo_email).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            full_name="Demo User",
            email=demo_email,
            phone="9876543999",
            password_hash=hash_password("password123"),
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
            preferred_language="en",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created demo user: {demo_email}")
    else:
        print(f"Demo user {demo_email} already exists.")
        
    other_email = "other@example.com"
    other_user = db.query(User).filter_by(email=other_email).first()
    if not other_user:
        other_user = User(
            id=uuid.uuid4(),
            full_name="Other User",
            email=other_email,
            phone="9998887999",
            password_hash=hash_password("password123"),
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
            preferred_language="en",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

    # 2. Setup routes and buses for the specific booking requirements
    now = datetime.now()
    
    # Define route requirements from user prompt
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

    # 3. Create specific Bookings with EXACT requirements
    # Booking 1: Delhi -> Jaipur, BK-1234, Confirmed/Paid/On Time
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
        print(f"Created {b1_code}")

    # Booking 2: Mumbai -> Pune, BK-5678, Delayed 25 mins
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
        print(f"Created {b2_code}")

    # Booking 3: Bengaluru -> Chennai, BK-2468, Cancelled/Refund Processing
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
            payment_status=PaymentStatus.PAID,  # Paid but needs refund
        )
        db.add(b3)
        db.commit()
        print(f"Created {b3_code}")

    # Booking 4: Hyderabad -> Vijayawada, BK-1357, Pending/Pending
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
        print(f"Created {b4_code}")

    # Booking 5: Dehradun -> Delhi, BK-9876, Confirmed/Paid/In Transit
    b5_code = "BK-9876"
    if not db.query(Booking).filter_by(booking_code=b5_code).first():
        route = routes_dict["Dehradun-Delhi"]
        dep = now.replace(hour=22, minute=0, second=0, microsecond=0) - timedelta(hours=2) # Left 2 hours ago
        arr = dep + timedelta(hours=6, minutes=30)
        t5 = Trip(
            id=uuid.uuid4(),
            route_id=route.id,
            bus_id=buses_dict[4].id,
            departure_time=dep,
            arrival_time=arr,
            status=TripStatus.SCHEDULED, # In Transit technically (SCHEDULED is closest enum we have for running)
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
        print(f"Created {b5_code}")
        
    # Give the other user a booking to test unauthorized access
    b6_code = "BK-9999"
    if not db.query(Booking).filter_by(booking_code=b6_code).first():
        b6 = Booking(
            booking_code=b6_code,
            user_id=other_user.id,
            trip_id=db.query(Trip).first().id,
            seat_number="Z99",
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID
        )
        db.add(b6)
        db.commit()
        print(f"Created {b6_code} for Other User")

    print("Seed complete! Demo users and bookings are ready.")

if __name__ == "__main__":
    seed_database()
