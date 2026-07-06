from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.controllers.booking_controller import BookingController
from app.database.session import get_db
from app.utils.response import success_response

from app.auth.dependencies import get_optional_current_user

router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["Bookings"],
)

@router.get("")
def get_all_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    controller = BookingController(db)
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    return controller.get_all_bookings(user_id=user_id)

@router.get("/{booking_code}")
def get_booking(
    booking_code: str,
    db: Session = Depends(get_db),
):

    controller = BookingController(db)

    booking = controller.get_booking(
        booking_code
    )

    return {
    "booking_code": booking["booking_code"],
    "seat_number": booking["seat_number"],
    "booking_status": booking["booking_status"],
    "payment_status": booking["payment_status"],
    "bus_name": booking["bus_name"],
    "source": booking["source"],
    "destination": booking["destination"],
    "departure_time": booking["departure_time"],
    "arrival_time": booking["arrival_time"],
}