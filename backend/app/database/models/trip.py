import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class TripStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ON_TIME = "ON_TIME"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Trip(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "trips"

    route_id: Mapped[str] = mapped_column(
        ForeignKey("routes.id"),
        nullable=False,
    )

    bus_id: Mapped[str] = mapped_column(
        ForeignKey("buses.id"),
        nullable=False,
    )

    departure_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus),
        default=TripStatus.SCHEDULED,
        nullable=False,
    )

    delay_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Human-readable delay reason, e.g. "Heavy traffic near Nagpur"
    delay_reason: Mapped[str] = mapped_column(
        String(300),
        nullable=True,
    )

    # Simulated/demo current location for bus tracking
    # e.g. "Approaching Nagpur, ~120 km from Mumbai"
    # NOTE: This is demo data, NOT a live GPS feed.
    current_location: Mapped[str] = mapped_column(
        String(200),
        nullable=True,
    )

    # Updated ETA when bus is delayed (nullable, only set when delayed)
    updated_eta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    available_seats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    route = relationship(
        "Route",
        back_populates="trips",
    )

    bus = relationship(
        "Bus",
        back_populates="trips",
    )

    bookings = relationship(
        "Booking",
        back_populates="trip",
    )