from sqlalchemy.orm import Session

from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class BookingController:

    def __init__(self, db: Session):

        repository = BookingRepository(db)

        self.service = BookingService(repository)

    def get_booking(self, booking_code: str):
        return self.service.get_booking_details(booking_code)
    
    def get_all_bookings(self):

        return self.service.get_all_bookings()