from app.exceptions.common import NotFoundException
from app.repositories.trip_repository import TripRepository


def _fmt_dt(dt) -> str | None:
    """Safely format a datetime to a human-readable string."""
    if dt is None:
        return None
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


class TripService:

    def __init__(self, repository: TripRepository):
        self.repository = repository

    def get_trip_from_booking(self, booking_code: str):
        """Used by DelayTool to get trip/delay details for a booking."""
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
            "delay_reason": trip.delay_reason if trip.delay_reason else None,
            "current_location": trip.current_location if trip.current_location else None,
            "departure_time": _fmt_dt(trip.departure_time),
            "arrival_time": _fmt_dt(trip.arrival_time),
            "updated_eta": _fmt_dt(trip.updated_eta) if trip.updated_eta else None,
            "bus_name": trip.bus.bus_name,
            "bus_number": trip.bus.bus_number,
            "source": trip.route.source_city,
            "destination": trip.route.destination_city,
        }

    def get_bus_tracking(self, booking_code: str):
        """
        Used by TrackingTool. Returns current location and ETA.
        NOTE: This is SIMULATED/DEMO data stored in the Trip.current_location field.
        It is NOT a live GPS feed.
        """
        trip = self.repository.get_current_location(booking_code)

        if trip is None:
            raise NotFoundException(
                "Booking not found"
            )

        return {
            "current_location": trip.current_location if trip.current_location else None,
            "trip_status": trip.status.value,
            "delay_minutes": trip.delay_minutes,
            "delay_reason": trip.delay_reason if trip.delay_reason else None,
            "arrival_time": _fmt_dt(trip.arrival_time),
            "updated_eta": _fmt_dt(trip.updated_eta) if trip.updated_eta else None,
            "is_simulated": True,  # Always True — this is NOT live GPS
        }