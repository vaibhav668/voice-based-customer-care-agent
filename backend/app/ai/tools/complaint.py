from sqlalchemy.orm import Session

from app.repositories.booking_repository import BookingRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.booking_service import BookingService


class ComplaintTool:

    def __init__(self, db: Session):
        self.booking_service = BookingService(BookingRepository(db))
        self.service = ComplaintService(
            ComplaintRepository(db),
            BookingRepository(db),
        )

    def execute(
        self,
        booking_code: str,
        complaint: str,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):
        # Verify ownership securely first
        self.booking_service.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)
        return self.service.register(
            booking_code=booking_code,
            description=complaint,
            user_id=user_id,
            session_phone=session_phone,
        )