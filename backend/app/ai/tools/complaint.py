from sqlalchemy.orm import Session

from app.repositories.booking_repository import BookingRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService


class ComplaintTool:

    def __init__(self, db: Session):

        self.service = ComplaintService(
            ComplaintRepository(db),
            BookingRepository(db),
        )

    def execute(
        self,
        booking_code,
        description,
    ):

        return self.service.register(
            booking_code,
            description,
        )