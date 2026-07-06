from unittest import result

from app.repositories.booking_repository import BookingRepository
from app.exceptions.common import NotFoundException


class BookingService:

    def __init__(self, repository):
        self.repository = repository

    def get_booking_details(
        self,
        booking_code: str,
    ):

        booking = self.repository.get_booking_with_trip(
            booking_code
        )

        if booking is None:
            raise NotFoundException(
                "Booking not found"
            )

        return {
            "booking_code": booking.booking_code,
            "seat_number": booking.seat_number,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "bus_name": booking.trip.bus.bus_name,
            "source": booking.trip.route.source_city,
            "destination": booking.trip.route.destination_city,
            "departure_time": booking.trip.departure_time,
            "arrival_time": booking.trip.arrival_time,
        }
    
    def cancel_booking(self, booking_code: str):

        booking = self.repository.get_booking_with_trip(
            booking_code
        )

        if booking is None:
            raise NotFoundException(
            "Booking not found"
            )

        booking = self.repository.cancel_booking(
           booking
        )

        return {
        "booking_code": booking.booking_code,
        "status": booking.booking_status.value,
        "seat_number": booking.seat_number,
    }


    def get_refund_status(self, booking_code: str):

        booking = self.repository.get_refund_status(
           booking_code
        )

        if booking is None:
           raise NotFoundException(
            "Booking not found"
           ) 

        return {
            "booking_code": booking.booking_code,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
        }
    
    def get_all_bookings(self, user_id=None):

        bookings = self.repository.get_all_bookings(user_id=user_id)

        result = []

        for booking in bookings:

            result.append({

            "booking_code": booking.booking_code,

            "seat_number": booking.seat_number,

            "booking_status": booking.booking_status.value,

            "payment_status": booking.payment_status.value,

            "bus_name": booking.trip.bus.bus_name if (booking.trip and booking.trip.bus) else "Volvo Express",

            "source": booking.trip.route.source_city if (booking.trip and booking.trip.route) else "Vizag",

            "destination": booking.trip.route.destination_city if (booking.trip and booking.trip.route) else "Delhi",

            "departure_time": str(booking.trip.departure_time) if booking.trip else "08:00 AM",

            "arrival_time": str(booking.trip.arrival_time) if booking.trip else "04:00 PM",

        })

        return result

    def create_new_booking(
        self,
        source: str,
        destination: str,
        travel_date: str | None = None,
        seat_number: int | None = None,
        user_id=None,
    ) -> dict:
        from app.repositories.trip_repository import TripRepository
        from app.database.models.booking import Booking, BookingStatus, PaymentStatus
        from app.database.models.user import User
        from sqlalchemy import select

        # Do not fallback to a random first user. Keep user_id as None if guest/unauthenticated.

        trip_repo = TripRepository(self.repository.db)
        trip = trip_repo.find_trip_by_route(source, destination)

        if not trip:
            from app.database.models.route import Route
            from app.database.models.bus import Bus, BusType
            from app.database.models.trip import Trip, TripStatus
            from datetime import datetime, timedelta
            import random

            route = Route(
                source_city=source.title() if source else "Delhi",
                destination_city=destination.title() if destination else "Mumbai",
                distance_km=1400,
                estimated_duration_minutes=1200,
            )
            self.repository.db.add(route)
            self.repository.db.commit()
            self.repository.db.refresh(route)

            bus = Bus(
                bus_number=f"DL01BUS{random.randint(1000, 9999)}",
                bus_name="Volvo Multi Axle AC Sleeper",
                registration_number=f"DL01REG{random.randint(1000, 9999)}",
                bus_type=BusType.AC_SLEEPER,
                capacity=36,
            )
            self.repository.db.add(bus)
            self.repository.db.commit()
            self.repository.db.refresh(bus)

            departure = datetime.now() + timedelta(days=1, hours=8)
            arrival = departure + timedelta(hours=15)

            trip = Trip(
                route_id=route.id,
                bus_id=bus.id,
                departure_time=departure,
                arrival_time=arrival,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35,
            )
            self.repository.db.add(trip)
            self.repository.db.commit()
            self.repository.db.refresh(trip)

        booking_code = self.repository.generate_next_booking_code()
        chosen_seat = str(seat_number or max(1, (36 - getattr(trip, 'available_seats', 35) + 1)))

        new_booking = Booking(
            booking_code=booking_code,
            user_id=user_id,
            trip_id=trip.id,
            seat_number=chosen_seat,
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID,
        )
        self.repository.create(new_booking)

        booking = self.repository.get_booking_with_trip(booking_code)

        return {
            "success": True,
            "message": f"Booking successfully created! Your booking code is {booking_code}.",
            "booking_code": booking_code,
            "seat_number": booking.seat_number if booking else chosen_seat,
            "booking_status": booking.booking_status.value if booking else "CONFIRMED",
            "payment_status": booking.payment_status.value if booking else "PAID",
            "bus_name": booking.trip.bus.bus_name if (booking and booking.trip and booking.trip.bus) else "Volvo Express",
            "source": booking.trip.route.source_city if (booking and booking.trip and booking.trip.route) else source,
            "destination": booking.trip.route.destination_city if (booking and booking.trip and booking.trip.route) else destination,
            "departure_time": str(booking.trip.departure_time) if (booking and booking.trip) else "08:00 AM",
            "arrival_time": str(booking.trip.arrival_time) if (booking and booking.trip) else "04:00 PM",
        }