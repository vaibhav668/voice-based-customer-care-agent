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
        travel_date: str | None = None,
        confirmation: str | None = None,
        user_id: str | None = None,
        session_phone: str | None = None,
    ):
        """Checks rescheduling eligibility and processes travel date updates if confirmed."""
        # Securely verify ownership first
        booking_details = self.service.get_booking_details_secure(booking_code, user_id, session_phone=session_phone)
        
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
            
        fee = "₹50"
        try:
            # Parse departure string (e.g. "2026-07-06 18:30")
            departure = datetime.strptime(departure_str, "%Y-%m-%d %H:%M")
            now = datetime.now()
            
            diff_hours = (departure - now).total_seconds() / 3600
            
            if diff_hours < 6:
                return {
                    "reschedule_eligible": False,
                    "message": "Rescheduling is only allowed up to 6 hours before departure. This booking can no longer be rescheduled.",
                    "booking": booking_details
                }
            elif diff_hours <= 24:
                fee = "₹100"
        except Exception:
            pass

        # Perform rescheduling if travel date and confirmation are present
        if travel_date and confirmation and confirmation.strip().lower() in ["yes", "yes reschedule", "confirm", "proceed", "go ahead", "yes cancel"]:
            try:
                res = self.service.reschedule_booking(booking_code, travel_date, user_id=user_id, session_phone=session_phone)
                return {
                    "reschedule_eligible": True,
                    "status": "rescheduled",
                    "fee": fee,
                    "message": f"Successfully rescheduled booking {booking_code} to {res.get('departure_time')} with a fee of {fee}.",
                    "result": res
                }
            except Exception as e:
                return {
                    "reschedule_eligible": False,
                    "message": f"Failed to reschedule booking: {str(e)}",
                    "booking": booking_details
                }

        # Ask for confirmation if date is specified
        if travel_date:
            return {
                "reschedule_eligible": True,
                "fee": fee,
                "status": "confirmation_required",
                "message": f"Your booking {booking_code} is eligible for rescheduling to {travel_date} for a fee of {fee}. Please confirm to proceed.",
                "travel_date": travel_date,
                "requires_confirmation": True,
                "booking": booking_details
            }

        return {
            "reschedule_eligible": True,
            "fee": fee,
            "status": "date_required",
            "message": f"Your booking {booking_code} is eligible for rescheduling for a fee of {fee}. What is your preferred new travel date?",
            "booking": booking_details
        }
