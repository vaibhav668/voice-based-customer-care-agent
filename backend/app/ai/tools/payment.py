from sqlalchemy.orm import Session
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class PaymentTool:

    def __init__(self, db: Session):
        repository = BookingRepository(db)
        self.service = BookingService(repository)

    def execute(
        self,
        booking_code: str,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):
        """Retrieves payment details for a booking."""
        booking_details = self.service.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)
        
        status = booking_details.get("payment_status")
        if status == "PAID":
            message = "Your payment was successful and the booking is confirmed."
        elif status == "PENDING":
            message = "Your payment is currently pending. If money was deducted, it will automatically update within 15-30 minutes. Do not retry payment."
        elif status == "FAILED":
            message = "Your payment failed. If money was deducted, it will be automatically refunded by your bank within 3-5 working days."
        elif status == "REFUNDED":
            message = "Your payment has been refunded."
        else:
            message = "Unknown payment status. Please contact support."
            
        return {
            "booking_code": booking_code,
            "payment_status": status,
            "message": message,
            "booking_status": booking_details.get("booking_status")
        }
