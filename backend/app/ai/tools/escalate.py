from sqlalchemy.orm import Session
from app.repositories.conversation_repository import ConversationRepository

class EscalateTool:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ConversationRepository(db)

    def execute(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
    ):
        """Escalates the current conversation to a human support agent."""
        if session_id:
            conv = self.repo.get_by_session_id(session_id)
            if conv:
                conv.resolution_status = "escalated"
                self.db.commit()
                return {
                    "success": True,
                    "session_id": session_id,
                    "message": "Connecting you to a live support representative. Please hold.",
                }
        return {
            "success": True,
            "message": "Connecting you to a live support representative. Please hold.",
        }
