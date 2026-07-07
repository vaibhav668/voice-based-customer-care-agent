import uuid
from datetime import datetime
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, Session

from app.database.models.conversation import Conversation, ConversationStatus, ConversationChannel
from app.database.models.conversation_message import ConversationMessage
from app.database.models.user import User
from app.repositories.base_repository import BaseRepository


class ConversationRepository(BaseRepository):

    def get_or_create_session(
        self,
        session_id: str,
        user_id: str | None = None,
        channel: str = "CHAT",
        language: str = "en",
    ) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.is_deleted == False,
        )
        conv = self.db.scalar(stmt)

        if conv:
            if user_id and not conv.user_id:
                conv.user_id = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            if language:
                conv.language = language
            self.db.commit()
            self.db.refresh(conv)
            return conv

        # Convert user_id if string
        uid = None
        if user_id:
            try:
                uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            except Exception:
                uid = None

        new_conv = Conversation(
            session_id=session_id,
            user_id=uid,
            status=ConversationStatus.ACTIVE,
            channel=ConversationChannel.VOICE if channel.upper() == "VOICE" else ConversationChannel.CHAT,
            language=language or "en",
            message_count=0,
        )
        self.db.add(new_conv)
        self.db.commit()
        self.db.refresh(new_conv)
        return new_conv

    def get_by_id(self, conversation_id: str) -> Conversation | None:
        try:
            cid = conversation_id if isinstance(conversation_id, uuid.UUID) else uuid.UUID(str(conversation_id))
        except Exception:
            return None

        stmt = (
            select(Conversation)
            .options(joinedload(Conversation.messages))
            .where(
                Conversation.id == cid,
                Conversation.is_deleted == False,
            )
        )
        return self.db.scalar(stmt)

    def get_by_session_id(self, session_id: str) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.is_deleted == False,
        )
        return self.db.scalar(stmt)

    def list_conversations(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        query = select(Conversation).where(Conversation.is_deleted == False)

        if user_id:
            try:
                uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
                # ONLY show conversations belonging to this user (strict match)
                query = query.where(Conversation.user_id == uid)
            except Exception:
                # If user_id is invalid, return nothing for safety
                query = query.where(Conversation.user_id == None)
        else:
            # Guest/unauthenticated: only anonymous conversations
            query = query.where(Conversation.user_id == None)

        if channel:
            query = query.where(Conversation.channel == channel.upper())

        if status:
            query = query.where(Conversation.status == status.upper())

        count_stmt = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_stmt) or 0

        query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
        conversations = list(self.db.scalars(query).all())

        return total, conversations

    def search_conversations(
        self,
        search_query: str | None = None,
        booking_code: str | None = None,
        intent: str | None = None,
        language: str | None = None,
        user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        query = select(Conversation).where(Conversation.is_deleted == False)

        if user_id:
            try:
                uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
                # ONLY show conversations belonging to this user (strict match)
                query = query.where(Conversation.user_id == uid)
            except Exception:
                query = query.where(Conversation.user_id == None)
        else:
            query = query.where(Conversation.user_id == None)

        if language:
            query = query.where(Conversation.language == language.lower())

        if intent:
            query = query.where(Conversation.current_intent == intent)

        if booking_code or search_query:
            subq = select(ConversationMessage.conversation_id).distinct()
            conditions = []
            if booking_code:
                conditions.append(ConversationMessage.booking_code.ilike(f"%{booking_code}%"))
            if search_query:
                term = f"%{search_query}%"
                conditions.append(ConversationMessage.message.ilike(term))
                conditions.append(ConversationMessage.booking_code.ilike(term))
                conditions.append(ConversationMessage.entities.ilike(term))
                conditions.append(ConversationMessage.intent.ilike(term))

            subq = subq.where(or_(*conditions))
            query = query.where(Conversation.id.in_(subq))

        count_stmt = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_stmt) or 0

        query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
        conversations = list(self.db.scalars(query).all())

        return total, conversations

    def update_state(
        self,
        conversation_id,
        current_intent: str | None = None,
        last_tool: str | None = None,
        language: str | None = None,
    ):
        conv = self.db.get(Conversation, conversation_id)
        if conv:
            if current_intent:
                conv.current_intent = current_intent
            if last_tool:
                conv.last_tool = last_tool
            if language:
                conv.language = language
            conv.message_count += 1
            conv.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(conv)
        return conv

    def soft_delete(self, conversation_id) -> bool:
        conv = self.db.get(Conversation, conversation_id)
        if conv:
            conv.is_deleted = True
            conv.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
