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
        session_phone: str | None = None,
    ):
        # Retrieve refund status passing user_id and session_phone for secure authorization
        return self.service.get_refund_status(
            booking_code,
            user_id=user_id,
            session_phone=session_phone,
        )