from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin

class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    start_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )
