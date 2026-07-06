import json
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.conversation_message import ConversationMessage, MessageSender, MessageType
from app.repositories.base_repository import BaseRepository


class ConversationMessageRepository(BaseRepository):

    def add_message(
        self,
        conversation_id,
        sender: str,
        message_type: str,
        message: str,
        intent: str | None = None,
        confidence: float | None = None,
        entities: dict | str | None = None,
        tool_used: str | None = None,
        response_time_ms: float | None = None,
        audio_path: str | None = None,
        booking_code: str | None = None,
    ) -> ConversationMessage:

        cid = conversation_id if isinstance(conversation_id, uuid.UUID) else uuid.UUID(str(conversation_id))

        entities_str = None
        if entities:
            if isinstance(entities, dict):
                entities_str = json.dumps(entities, default=str)
            else:
                entities_str = str(entities)

        sender_enum = MessageSender.USER if sender.upper() == "USER" else (
            MessageSender.AI if sender.upper() == "AI" else MessageSender.SYSTEM
        )

        type_enum = MessageType.VOICE if message_type.upper() == "VOICE" else MessageType.TEXT

        msg = ConversationMessage(
            conversation_id=cid,
            sender=sender_enum,
            message_type=type_enum,
            message=message,
            intent=intent,
            confidence=confidence,
            entities=entities_str,
            tool_used=tool_used,
            response_time_ms=response_time_ms,
            audio_path=audio_path,
            booking_code=booking_code,
        )

        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages_for_conversation(self, conversation_id) -> list[ConversationMessage]:
        cid = conversation_id if isinstance(conversation_id, uuid.UUID) else uuid.UUID(str(conversation_id))
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == cid)
            .order_by(ConversationMessage.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
