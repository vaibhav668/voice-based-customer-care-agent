from sqlalchemy.orm import Session
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class ListBookingsTool:

    def __init__(self, db: Session):
        repository = BookingRepository(db)
        self.service = BookingService(repository)

    def execute(
        self,
        user_id: str | None = None,
    ):
        if not user_id:
            return {
                "status": "error",
                "message": "User is not authenticated. Cannot retrieve booking history."
            }
            
        bookings = self.service.get_all_bookings(user_id=user_id)
        
        if not bookings:
            return {
                "status": "success",
                "message": "You do not have any upcoming or previous bookings.",
                "bookings": []
            }
            
        return {
            "status": "success",
            "message": f"Found {len(bookings)} bookings in your history.",
            "bookings": bookings
        }
