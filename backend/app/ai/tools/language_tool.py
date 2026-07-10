from sqlalchemy.orm import Session
from app.repositories.conversation_repository import ConversationRepository
from app.database.models.user import User

class LanguageTool:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ConversationRepository(db)

    def execute(
        self,
        language: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ):
        """Updates the conversation and user preferred language."""
        if not language:
            return {
                "success": False,
                "message": "No language code specified.",
            }

        # Normalize code
        lang = language.lower()
        # Accept spelling/full names too
        lang_map = {
            "english": "en",
            "hindi": "hi",
            "marathi": "mr",
            "telugu": "te",
            "tamil": "ta",
            "kannada": "kn",
            "gujarati": "gu",
            "bengali": "bn",
            "malayalam": "ml",
            "urdu": "ur"
        }
        if lang in lang_map:
            lang = lang_map[lang]

        if lang not in ("en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "ur"):
            return {
                "success": False,
                "message": f"Language {language} is not supported.",
            }

        # Update Conversation
        if session_id:
            conv = self.repo.get_by_session_id(session_id)
            if conv:
                conv.language = lang
                self.db.commit()

        # Update User
        if user_id:
            import uuid
            try:
                uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
                user = self.db.get(User, uid)
                if user:
                    user.preferred_language = lang
                    self.db.commit()
            except Exception:
                pass

        return {
            "success": True,
            "language": lang,
            "message": f"Language successfully updated to {lang}.",
        }
