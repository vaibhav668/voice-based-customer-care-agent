from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationSession:

    session_id: str

    # Current conversation state
    current_intent: str | None = None
    language: str = "en"

    # Extracted entities
    entities: dict = field(default_factory=dict)

    # Previous conversation
    last_tool: str | None = None

    last_result: dict | None = None

    last_response: str | None = None

    # Chat history
    history: list = field(default_factory=list)

    # Time
    created_at: datetime = field(default_factory=datetime.now)

    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(
        self,
        role: str,
        message: str,
    ):

        self.history.append(
            {
                "role": role,
                "message": message,
            }
        )

        # Keep only last 20 messages

        self.history = self.history[-20:]

        self.updated_at = datetime.now()