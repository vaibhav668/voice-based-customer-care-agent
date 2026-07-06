import enum
from sqlalchemy import Float, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class MessageSender(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"


class MessageType(str, enum.Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"


class ConversationMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversation_messages"

    conversation_id = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender: Mapped[MessageSender] = mapped_column(
        Enum(MessageSender),
        nullable=False,
    )

    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType),
        default=MessageType.TEXT,
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    translated_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    entities: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    tool_used: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )

    response_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    audio_path: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    booking_code: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    conversation = relationship("Conversation", back_populates="messages")
