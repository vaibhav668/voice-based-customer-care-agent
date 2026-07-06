from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator


class ConversationMessageSchema(BaseModel):
    id: UUID | str
    conversation_id: UUID | str
    sender: str
    message_type: str
    message: str
    translated_message: str | None = None
    intent: str | None = None
    confidence: float | None = None
    entities: dict | str | None = None
    tool_used: str | None = None
    response_time_ms: float | None = None
    audio_path: str | None = None
    booking_code: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "conversation_id", mode="before")
    @classmethod
    def stringify_uuids(cls, v):
        if v is not None:
            return str(v)
        return v


class ConversationSchema(BaseModel):
    id: UUID | str
    session_id: str
    user_id: UUID | str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str
    language: str
    channel: str
    current_intent: str | None = None
    last_tool: str | None = None
    message_count: int = 0
    summary: str | None = None
    sentiment: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def stringify_uuids(cls, v):
        if v is not None:
            return str(v)
        return v


class ConversationDetailSchema(ConversationSchema):
    messages: list[ConversationMessageSchema] = []


class PaginatedConversationsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    conversations: list[ConversationSchema]
