from sqlalchemy.orm import Session
from app.repositories.trip_repository import TripRepository
from app.services.trip_service import TripService
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class TrackingTool:

    def __init__(self, db: Session):
        trip_repo = TripRepository(db)
        self.trip_service = TripService(trip_repo)
        
        booking_repo = BookingRepository(db)
        self.booking_service = BookingService(booking_repo)

    def execute(
        self,
        booking_code: str,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):
        # Securely verify ownership first
        self.booking_service.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)
        
        return self.trip_service.get_bus_tracking(booking_code)
