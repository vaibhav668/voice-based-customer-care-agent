from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.controllers.trip_controller import TripController
from app.database.session import get_db

router = APIRouter()


@router.get("/{booking_code}")
def get_trip(
    booking_code: str,
    db: Session = Depends(get_db),
):

    controller = TripController(db)

    trip = controller.get_trip(
        booking_code
    )

    return {
        "success": True,
        "data": trip,
    }