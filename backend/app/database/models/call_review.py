from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin

class CallReview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "call_reviews"

    call_id = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    admin_id = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    outcome_tag: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    notes: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    call = relationship("Conversation", backref="reviews")
    admin = relationship("User", backref="reviews")
