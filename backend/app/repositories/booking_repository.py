from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models.booking import Booking, BookingStatus
from app.database.models.trip import Trip
from app.repositories.base_repository import BaseRepository


class BookingRepository(BaseRepository):

    def get_by_booking_code(
        self,
        booking_code: str,
    ) -> Booking | None:

        stmt = (
            select(Booking)
            .where(Booking.booking_code == booking_code)
        )

        return self.db.scalar(stmt)

    def create(
        self,
        booking: Booking,
    ) -> Booking:

        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)

        return booking

    def update(
        self,
        booking: Booking,
    ) -> Booking:

        self.db.commit()
        self.db.refresh(booking)

        return booking
    
    def get_booking_with_trip(
        self,
        booking_code: str,
    ) -> Booking | None:
        
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.trip).joinedload(Trip.bus),
                joinedload(Booking.trip).joinedload(Trip.route)
            )
            .where(Booking.booking_code == booking_code)
        )
 
        return self.db.scalar(stmt)

    def cancel_booking(
        self, 
        booking: Booking,
    ) -> Booking:

        booking.booking_status = BookingStatus.CANCELLED

        self.db.commit()
        self.db.refresh(booking)

        return booking
    
    def get_refund_status(self, booking_code: str):
        return self.get_booking_with_trip(booking_code)
    
    def get_all_bookings(self, user_id=None) -> list[Booking]:
        from sqlalchemy import or_
        import uuid

        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.trip).joinedload(Trip.bus),
                joinedload(Booking.trip).joinedload(Trip.route),
            )
        )

        if user_id:
            try:
                uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
                # Filter by authenticated user's ID OR show guest/unassigned bookings (user_id is Null)
                stmt = stmt.where(or_(Booking.user_id == uid, Booking.user_id == None))
            except Exception:
                pass

        stmt = stmt.order_by(Booking.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def generate_next_booking_code(self) -> str:
        count = self.db.query(Booking).count()
        return f"BK-{100001 + count}"