from sqlalchemy.orm import Session
from app.database.models.user import User

class ProfileTool:
    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        user_id: str | None = None,
    ):
        """Retrieves profile details for the authenticated user."""
        if not user_id:
            return {
                "success": False,
                "message": "You are not logged in. Please log in to access your profile details.",
            }

        import uuid
        try:
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        except Exception:
            return {
                "success": False,
                "message": "Invalid user ID.",
            }

        user = self.db.get(User, uid)
        if not user:
            return {
                "success": False,
                "message": "User profile not found.",
            }

        return {
            "success": True,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "preferred_language": user.preferred_language,
        }
