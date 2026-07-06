from datetime import datetime, timedelta

from app.database.session import SessionLocal
from app.database.models.user import User, UserRole
from app.database.models.route import Route
from app.database.models.bus import Bus, BusType
from app.database.models.trip import Trip, TripStatus
from app.database.models.booking import (
    Booking,
    BookingStatus,
    PaymentStatus,
)

db = SessionLocal()

try:
    # Don't seed twice
    existing = db.query(Booking).filter(
        Booking.booking_code == "BK-100001"
    ).first()

    if existing:
        print("Database already seeded.")
        exit()

    print("Seeding database...")

    # ---------------- USERS ---------------- #

    user = User(
        full_name="Vaibhav Pokhriyal",
        email="vaibhav@gmail.com",
        phone="9876543210",
        password_hash="dummy_hash",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # ---------------- ROUTE ---------------- #

    route = Route(
        source_city="Vizag",
        destination_city="Delhi",
        distance_km=1750,
        estimated_duration_minutes=1680,
    )

    db.add(route)
    db.commit()
    db.refresh(route)

    # ---------------- BUS ---------------- #

    bus = Bus(
        bus_number="AP39AB1001",
        bus_name="Volvo Multi Axle",
        registration_number="AP39BUS1001",
        bus_type=BusType.AC_SLEEPER,
        capacity=36,
    )

    db.add(bus)
    db.commit()
    db.refresh(bus)

    # ---------------- TRIP ---------------- #

    departure = datetime.now() + timedelta(hours=2)

    arrival = departure + timedelta(hours=28)

    trip = Trip(
        route_id=route.id,
        bus_id=bus.id,
        departure_time=departure,
        arrival_time=arrival,
        status=TripStatus.DELAYED,
        delay_minutes=20,
        available_seats=35,
    )

    db.add(trip)
    db.commit()
    db.refresh(trip)

    # ---------------- BOOKING ---------------- #

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

    print("Database seeded successfully!")

finally:
    db.close()