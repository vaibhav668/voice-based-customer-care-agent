from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.database.models.complaint import Complaint
from app.database.models.booking import Booking
from app.database.models.user import User
from app.database.models.trip import Trip
from app.database.models.route import Route
from app.exceptions.common import UnauthorizedException
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/complaints",
    tags=["Complaints"],
)

@router.get("")
def list_complaints(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = current_user.get("role") if current_user else None
    if role != "ADMIN":
        raise UnauthorizedException("Only administrators can access complaint records")

    # Load complaints, along with linked bookings, users, and trips/routes
    complaints = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.booking)
            .joinedload(Booking.user),
            joinedload(Complaint.booking)
            .joinedload(Booking.trip)
            .joinedload(Trip.route)
        )
        .order_by(Complaint.created_at.desc())
        .all()
    )

    result = []
    for c in complaints:
        booking = c.booking
        user = booking.user if booking else None
        trip = booking.trip if booking else None
        route = trip.route if trip else None

        result.append({
            "id": str(c.id),
            "complaint_code": c.complaint_code,
            "title": c.title,
            "description": c.description,
            "status": c.status.value,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "booking_code": booking.booking_code if booking else None,
            "customer": {
                "name": user.full_name if user else "Guest Customer",
                "email": user.email if user else "N/A",
                "phone": user.phone if user else "N/A",
            },
            "trip": {
                "source": route.source_city if route else "N/A",
                "destination": route.destination_city if route else "N/A",
            }
        })

    return success_response(
        data=result,
        message="Complaints retrieved successfully"
    )
