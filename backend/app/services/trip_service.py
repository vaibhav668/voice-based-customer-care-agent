from app.exceptions.common import NotFoundException
from app.repositories.trip_repository import TripRepository


class TripService:

    def __init__(self, repository: TripRepository):
        self.repository = repository

    def get_trip_from_booking(self, booking_code: str):

        booking = self.repository.get_trip_by_booking_code(
            booking_code
        )

        if booking is None:
            raise NotFoundException(
                "Booking not found"
            )

        trip = booking.trip

        return {
        "booking_code": booking.booking_code,
        "trip_status": trip.status.value,
        "delay_minutes": trip.delay_minutes,
        "departure_time": trip.departure_time,
        "arrival_time": trip.arrival_time,
        "bus_name": trip.bus.bus_name,
        "source": trip.route.source_city,
        "destination": trip.route.destination_city,
    }

    def get_bus_location(self, booking_code: str):

        trip = self.repository.get_current_location(
            booking_code
        )

        if trip is None:
            raise NotFoundException(
                "Booking not found"
            )

        return {
            "location": trip.current_location,
            "delay": trip.delay_minutes,
            "arrival": trip.arrival_time,
        }