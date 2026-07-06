from sqlalchemy.orm import Session

from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class CancellationTool:

    def __init__(self, db: Session):

        self.service = BookingService(
            BookingRepository(db)
        )

    def execute(
        self,
        booking_code: str,
    ):

        return self.service.cancel_booking(
            booking_code
        )