from sqlalchemy.orm import Session
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class CancellationTool:

    def __init__(self, db: Session):
        repository = BookingRepository(db)
        self.service = BookingService(repository)

    def execute(
        self,
        booking_code: str,
        confirmation: str | None = None,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):
        """
        Executes cancellation if explicitly confirmed.
        Otherwise, returns a preview and signals that confirmation is needed.
        """
        # First ensure ownership securely
        booking_preview = self.service.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)
        
        if booking_preview.get("booking_status") == "CANCELLED":
            return {
                "status": "already_cancelled",
                "message": f"Booking {booking_code} is already cancelled.",
                "booking": booking_preview
            }

        # Check if the user has explicitly confirmed
        if confirmation and confirmation.strip().lower() in ["yes", "yes cancel", "confirm", "proceed", "go ahead"]:
            result = self.service.cancel_booking(booking_code)
            return {
                "status": "cancelled",
                "message": f"Successfully cancelled booking {booking_code}.",
                "result": result
            }

        # Return preview and flag for confirmation
        return {
            "status": "confirmation_required",
            "message": f"Found booking {booking_code} from {booking_preview.get('source')} to {booking_preview.get('destination')}. Please confirm you want to cancel.",
            "booking": booking_preview,
            "requires_confirmation": True
        }