from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class Route(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "routes"

    source_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    destination_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    estimated_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    trips = relationship(
        "Trip",
        back_populates="route",
    )