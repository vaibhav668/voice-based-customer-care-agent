import enum
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ConversationChannel(str, enum.Enum):
    CHAT = "CHAT"
    VOICE = "VOICE"


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    session_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ended_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )

    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(ConversationChannel),
        default=ConversationChannel.CHAT,
        nullable=False,
    )

    current_intent: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    last_tool: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    sentiment: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    user = relationship("User", backref="conversations")

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at.asc()",
    )
