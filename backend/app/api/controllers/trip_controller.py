from sqlalchemy.orm import Session

from app.repositories.trip_repository import TripRepository
from app.services.trip_service import TripService


class TripController:

    def __init__(self, db: Session):

        repository = TripRepository(db)

        self.service = TripService(repository)

    def get_trip(
        self,
        booking_code: str,
    ):

        return self.service.get_trip_from_booking(
            booking_code
        )