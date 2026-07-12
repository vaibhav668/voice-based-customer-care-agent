from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class CustomerFeedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customer_feedbacks"

    conversation_id = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    metadata_json: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    conversation = relationship("Conversation", backref="feedbacks")
    user = relationship("User", backref="feedbacks")
