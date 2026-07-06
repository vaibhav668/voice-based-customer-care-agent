from ast import stmt

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.database.models.booking import Booking
from app.database.models.trip import Trip
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService


class BookingTool:

    def __init__(self, db: Session):

        repository = BookingRepository(db)

        self.service = BookingService(repository)

    def execute(
        self,
        booking_code: str,
    ):

        return self.service.get_booking_details(
            booking_code
        )
    
    ''' def cancel(self, booking_code):

        return self.service.cancel_booking(
            booking_code
        )
    
    def refund(self, booking_code: str):

        return self.service.get_refund_status(
            booking_code
        ) '''    
 
    def get_booking_with_trip(
        self,
        booking_code: str,
        ):

        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.trip)
                .joinedload(Trip.bus),
 
                joinedload(Booking.trip)
                .joinedload(Trip.route),
            )
            .where( 
                Booking.booking_code == booking_code
            )
            )

        return self.db.scalar(stmt)