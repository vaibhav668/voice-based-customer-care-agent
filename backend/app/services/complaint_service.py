import uuid

from app.database.models.complaint import Complaint
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.booking_repository import BookingRepository


class ComplaintService:

    def __init__(
        self,
        complaint_repository: ComplaintRepository,
        booking_repository: BookingRepository,
    ):
        self.complaint_repository = complaint_repository
        self.booking_repository = booking_repository

    def register(
        self,
        booking_code: str,
        description: str,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):

        booking = self.booking_repository.get_booking_with_trip(
            booking_code
        )

        if booking is None:
            raise Exception("Booking not found")

        complaint = Complaint(
            complaint_code=f"CMP-{str(uuid.uuid4())[:8]}",
            booking_id=booking.id,
            title="Customer Complaint",
            description=description,
        )

        complaint = self.complaint_repository.create(
            complaint
        )

        return {
            "complaint_code": complaint.complaint_code,
            "status": complaint.status.value,
        }