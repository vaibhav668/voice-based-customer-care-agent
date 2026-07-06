import enum

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class BusType(str, enum.Enum):
    AC_SLEEPER = "AC_SLEEPER"
    NON_AC_SLEEPER = "NON_AC_SLEEPER"
    AC_SEATER = "AC_SEATER"
    NON_AC_SEATER = "NON_AC_SEATER"


class Bus(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "buses"

    bus_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    bus_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    registration_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )

    bus_type: Mapped[BusType] = mapped_column(
        Enum(BusType),
        nullable=False,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    trips = relationship(
        "Trip",
        back_populates="bus",
    )