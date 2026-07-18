from app.repositories.booking_repository import BookingRepository
from app.exceptions.common import NotFoundException


def _fmt_dt(dt) -> str | None:
    """Safely format a datetime to ISO string."""
    if dt is None:
        return None
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


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

        trip = booking.trip
        route = trip.route if trip else None
        bus = trip.bus if trip else None

        return {
            "booking_code": booking.booking_code,
            "seat_number": booking.seat_number,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "bus_name": bus.bus_name if bus else "N/A",
            "bus_number": bus.bus_number if bus else "N/A",
            "bus_type": bus.bus_type.value if bus else "N/A",
            "source": route.source_city if route else "N/A",
            "destination": route.destination_city if route else "N/A",
            "distance_km": route.distance_km if route else None,
            "boarding_point": route.source_city if route else "N/A",
            "drop_point": route.destination_city if route else "N/A",
            "departure_time": _fmt_dt(trip.departure_time) if trip else "N/A",
            "arrival_time": _fmt_dt(trip.arrival_time) if trip else "N/A",
            "trip_status": trip.status.value if trip else "N/A",
            "delay_minutes": trip.delay_minutes if trip else 0,
            "delay_reason": trip.delay_reason if (trip and trip.delay_reason) else None,
            "current_location": trip.current_location if (trip and trip.current_location) else None,
            "updated_eta": _fmt_dt(trip.updated_eta) if (trip and trip.updated_eta) else None,
        }

    def get_booking_details_secure(
        self,
        booking_code: str,
        user_id=None,
        session_phone: str | None = None,
    ):
        """
        Secure version: verifies that the booking belongs to the authenticated user.
        Raises NotFoundException if booking is not found OR belongs to a different user.
        """
        import uuid as _uuid
        booking = self.repository.get_booking_with_trip(booking_code)

        if booking is None:
            raise NotFoundException("No booking found with that code.")

        # Authorization check: if booking has a user_id, check ownership or phone number match.
        if booking.user_id:
            authorized = False
            # 1. Check logged-in user matching
            if user_id:
                try:
                    uid = _uuid.UUID(str(user_id))
                    booking_uid = _uuid.UUID(str(booking.user_id))
                    if uid == booking_uid:
                        authorized = True
                except (ValueError, AttributeError):
                    if str(user_id) == str(booking.user_id):
                        authorized = True
            
            # 2. Check phone verification if not authorized via user_id
            if not authorized and session_phone:
                clean_session_phone = "".join(filter(str.isdigit, str(session_phone)))[-10:]
                owner_phone = booking.user.phone if booking.user else None
                clean_owner_phone = "".join(filter(str.isdigit, str(owner_phone)))[-10:] if owner_phone else ""
                if clean_session_phone:
                    if clean_owner_phone and clean_session_phone == clean_owner_phone:
                        authorized = True
                    elif not clean_owner_phone:
                        # Allow access if owner record has no registered phone
                        authorized = True

            if not authorized:
                raise NotFoundException(
                    "You do not have permission to view this booking. Please verify your phone number first."
                )

        trip = booking.trip
        route = trip.route if trip else None
        bus = trip.bus if trip else None

        return {
            "booking_code": booking.booking_code,
            "seat_number": booking.seat_number,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "bus_name": bus.bus_name if bus else "N/A",
            "bus_number": bus.bus_number if bus else "N/A",
            "bus_type": bus.bus_type.value if bus else "N/A",
            "source": route.source_city if route else "N/A",
            "destination": route.destination_city if route else "N/A",
            "distance_km": route.distance_km if route else None,
            "boarding_point": route.source_city if route else "N/A",
            "drop_point": route.destination_city if route else "N/A",
            "departure_time": _fmt_dt(trip.departure_time) if trip else "N/A",
            "arrival_time": _fmt_dt(trip.arrival_time) if trip else "N/A",
            "trip_status": trip.status.value if trip else "N/A",
            "delay_minutes": trip.delay_minutes if trip else 0,
            "delay_reason": trip.delay_reason if (trip and trip.delay_reason) else None,
            "current_location": trip.current_location if (trip and trip.current_location) else None,
            "updated_eta": _fmt_dt(trip.updated_eta) if (trip and trip.updated_eta) else None,
        }

    def cancel_booking(self, booking_code: str, user_id=None, session_phone=None):
        # Securely verify ownership first
        self.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)

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

    def get_refund_status(self, booking_code: str, user_id=None, session_phone=None):
        # Securely verify ownership first
        self.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)

        booking = self.repository.get_refund_status(
            booking_code
        )

        if booking is None:
            raise NotFoundException(
                "Booking not found"
            )

        trip = booking.trip

        # Determine refund eligibility based on booking status and payment
        if booking.booking_status.value == "CANCELLED":
            if booking.payment_status.value == "REFUNDED":
                refund_message = "Your refund has been processed and credited to your original payment method."
            elif booking.payment_status.value == "PAID":
                refund_message = "Your booking has been cancelled. Refund is being processed and will arrive within 5-7 business days."
            else:
                refund_message = "Your booking is cancelled. Payment was not charged, so no refund is applicable."
        elif booking.booking_status.value == "CONFIRMED":
            refund_message = "Your booking is active and confirmed. No refund is applicable for an active booking."
        else:
            refund_message = "Please contact customer support for refund information."

        return {
            "booking_code": booking.booking_code,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "refund_message": refund_message,
            "departure_time": _fmt_dt(trip.departure_time) if trip else None,
            "source": trip.route.source_city if (trip and trip.route) else None,
            "destination": trip.route.destination_city if (trip and trip.route) else None,
        }

    def get_cancellation_preview(self, booking_code: str, user_id=None, session_phone=None):
        """
        Returns booking preview for the cancellation confirmation gate.
        Does NOT cancel the booking. Used to show what will be cancelled.
        """
        # Securely verify ownership first
        self.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)

        booking = self.repository.get_booking_with_trip(booking_code)

        if booking is None:
            raise NotFoundException("No booking found with that code.")

        trip = booking.trip
        route = trip.route if trip else None

        if booking.booking_status.value == "CANCELLED":
            return {
                "already_cancelled": True,
                "booking_code": booking.booking_code,
                "status": booking.booking_status.value,
                "message": "This booking is already cancelled.",
            }

        return {
            "already_cancelled": False,
            "booking_code": booking.booking_code,
            "seat_number": booking.seat_number,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "source": route.source_city if route else "N/A",
            "destination": route.destination_city if route else "N/A",
            "departure_time": _fmt_dt(trip.departure_time) if trip else "N/A",
        }

    def get_all_bookings(self, user_id=None):

        bookings = self.repository.get_all_bookings(user_id=user_id)

        result = []

        for booking in bookings:

            trip = booking.trip
            bus = trip.bus if trip else None
            route = trip.route if trip else None

            result.append({
                "booking_code": booking.booking_code,
                "seat_number": booking.seat_number,
                "booking_status": booking.booking_status.value,
                "payment_status": booking.payment_status.value,
                "bus_name": bus.bus_name if bus else "N/A",
                "source": route.source_city if route else "N/A",
                "destination": route.destination_city if route else "N/A",
                "departure_time": _fmt_dt(trip.departure_time) if trip else "N/A",
                "arrival_time": _fmt_dt(trip.arrival_time) if trip else "N/A",
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

        # Do NOT fall back to a random user — create as guest if no user_id provided
        # user_id stays None for anonymous/guest bookings

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
            "departure_time": _fmt_dt(booking.trip.departure_time) if (booking and booking.trip) else "N/A",
            "arrival_time": _fmt_dt(booking.trip.arrival_time) if (booking and booking.trip) else "N/A",
        }

    def reschedule_booking(self, booking_code: str, travel_date: str, user_id=None, session_phone=None) -> dict:
        """
        Executes rescheduling: finds a trip on the same route for the new travel date
        and updates the booking's trip association.
        """
        # Securely verify ownership first
        self.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)

        from app.repositories.trip_repository import TripRepository
        from app.database.models.trip import Trip, TripStatus
        from app.database.models.route import Route
        from app.database.models.bus import Bus, BusType
        from datetime import datetime, timedelta
        from sqlalchemy import select
        import random

        booking = self.repository.get_booking_with_trip(booking_code)
        if not booking:
            raise NotFoundException("Booking not found")

        trip = booking.trip
        route = trip.route if trip else None
        if not route:
            raise NotFoundException("Route not found for this booking")

        # Parse travel_date string (e.g. "2026-07-20")
        try:
            if " " in travel_date.strip():
                new_date = datetime.strptime(travel_date.strip(), "%Y-%m-%d %H:%M")
            else:
                new_date = datetime.strptime(travel_date.strip(), "%Y-%m-%d")
        except Exception:
            raise ValueError(f"Invalid date format: {travel_date}. Please use YYYY-MM-DD.")

        # Find trip on the same route for the target date
        trip_repo = TripRepository(self.repository.db)
        stmt = (
            select(Trip)
            .where(
                Trip.route_id == route.id,
                Trip.departure_time >= new_date.replace(hour=0, minute=0, second=0),
                Trip.departure_time <= new_date.replace(hour=23, minute=59, second=59),
            )
        )
        new_trip = self.repository.db.scalar(stmt)

        if not new_trip:
            # If no trip scheduled on that date, create one automatically
            departure = new_date.replace(hour=18, minute=30, second=0, microsecond=0)
            arrival = departure + (trip.arrival_time - trip.departure_time if trip else timedelta(hours=5))
            new_trip = Trip(
                route_id=route.id,
                bus_id=trip.bus_id if trip else None,
                departure_time=departure,
                arrival_time=arrival,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=35,
            )
            self.repository.db.add(new_trip)
            self.repository.db.commit()
            self.repository.db.refresh(new_trip)

        # Update the booking
        booking.trip_id = new_trip.id
        self.repository.db.commit()
        self.repository.db.refresh(booking)

        return {
            "success": True,
            "message": f"Booking {booking_code} successfully rescheduled to {_fmt_dt(new_trip.departure_time)}.",
            "booking_code": booking_code,
            "seat_number": booking.seat_number,
            "booking_status": booking.booking_status.value,
            "payment_status": booking.payment_status.value,
            "source": route.source_city,
            "destination": route.destination_city,
            "departure_time": _fmt_dt(new_trip.departure_time),
            "arrival_time": _fmt_dt(new_trip.arrival_time),
        }