import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    booking_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    trip_id = mapped_column(
        ForeignKey("trips.id"),
        nullable=False,
    )

    seat_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    booking_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        default=BookingStatus.CONFIRMED,
        nullable=False,
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.PAID,
        nullable=False,
    )

    booking_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user = relationship("User", back_populates="bookings")

    trip = relationship("Trip", back_populates="bookings")

    