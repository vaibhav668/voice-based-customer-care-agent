from sqlalchemy.orm import Session
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class RefundTool:

    def __init__(self, db: Session):
        repository = BookingRepository(db)
        self.service = BookingService(repository)

    def execute(
        self,
        booking_code: str,
        user_id: str | None = None,
    ):
        # We also enforce secure ownership here by checking details first
        self.service.get_booking_details_secure(booking_code, user_id)
        
        return self.service.get_refund_status(
            booking_code
        )