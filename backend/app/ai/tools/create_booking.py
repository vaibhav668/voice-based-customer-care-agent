from sqlalchemy.orm import Session

from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class CreateBookingTool:

    def __init__(self, db: Session):
        self.service = BookingService(
            BookingRepository(db)
        )

    def execute(
        self,
        source: str = "Delhi",
        destination: str = "Hyderabad",
        travel_date: str | None = None,
        seat_number: int | None = None,
        user_id=None,
    ):
        return self.service.create_new_booking(
            source=source or "Delhi",
            destination=destination or "Hyderabad",
            travel_date=travel_date,
            seat_number=seat_number,
            user_id=user_id,
        )
