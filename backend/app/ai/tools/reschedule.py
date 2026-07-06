from sqlalchemy.orm import Session
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService
from datetime import datetime


class RescheduleTool:

    def __init__(self, db: Session):
        repository = BookingRepository(db)
        self.service = BookingService(repository)

    def execute(
        self,
        booking_code: str,
        user_id: str | None = None,
    ):
        """Checks if a booking is eligible for rescheduling."""
        booking_details = self.service.get_booking_details_secure(booking_code, user_id)
        
        status = booking_details.get("booking_status")
        if status in ["CANCELLED", "COMPLETED"]:
            return {
                "reschedule_eligible": False,
                "message": f"This booking is {status} and cannot be rescheduled.",
                "booking": booking_details
            }

        departure_str = booking_details.get("departure_time")
        if not departure_str or departure_str == "N/A":
            return {
                "reschedule_eligible": False,
                "message": "Departure time not found. Please contact support.",
                "booking": booking_details
            }
            
        try:
            # Parse departure string (e.g. "2026-07-06 18:30")
            departure = datetime.strptime(departure_str, "%Y-%m-%d %H:%M")
            # Make it aware if needed (assuming local timezone or naive comparison is fine for demo)
            now = datetime.now()
            
            diff_hours = (departure - now).total_seconds() / 3600
            
            if diff_hours < 6:
                return {
                    "reschedule_eligible": False,
                    "message": "Rescheduling is only allowed up to 6 hours before departure. This booking can no longer be rescheduled.",
                    "booking": booking_details
                }
            elif diff_hours <= 24:
                return {
                    "reschedule_eligible": True,
                    "fee": "₹100",
                    "message": "This booking is eligible for rescheduling with a ₹100 fee. Please specify your desired new travel date.",
                    "booking": booking_details
                }
            else:
                return {
                    "reschedule_eligible": True,
                    "fee": "₹50",
                    "message": "This booking is eligible for rescheduling with a ₹50 fee. Please specify your desired new travel date.",
                    "booking": booking_details
                }
        except Exception:
            return {
                "reschedule_eligible": True,
                "message": "This booking appears eligible for rescheduling. Please contact support for date availability.",
                "booking": booking_details
            }
