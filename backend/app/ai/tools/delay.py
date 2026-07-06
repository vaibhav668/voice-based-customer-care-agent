from sqlalchemy.orm import Session
from app.repositories.trip_repository import TripRepository
from app.services.trip_service import TripService


class DelayTool:

    def __init__(self, db: Session):
        repository = TripRepository(db)
        self.service = TripService(repository)

    def execute(
        self,
        booking_code: str,
    ):
        return self.service.get_trip_from_booking(
            booking_code
        )