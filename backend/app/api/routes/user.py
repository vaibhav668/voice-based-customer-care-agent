from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)


from app.database.session import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.user import UpdateLanguageRequest
from sqlalchemy.orm import Session


@router.get("/me")
def get_profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user_id = current_user.get("sub") or current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    user = repo.get_by_id(user_id) if user_id else None

    profile_data = {
        "id": str(user.id) if user else current_user.get("sub"),
        "full_name": user.full_name if user else current_user.get("full_name", ""),
        "email": user.email if user else current_user.get("email", ""),
        "phone": user.phone if user else "",
        "role": user.role.value if (user and hasattr(user.role, "value")) else current_user.get("role", "CUSTOMER"),
        "preferred_language": getattr(user, "preferred_language", "en") if user else "en",
    }

    return success_response(
        data=profile_data,
        message="Profile fetched successfully",
    )


@router.put("/me/language")
def update_language(
    request: UpdateLanguageRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_languages = {"en", "hi", "mr", "te", "ta", "kn"}
    lang = request.preferred_language.lower()
    if lang not in valid_languages:
        lang = "en"

    repo = UserRepository(db)
    user_id = current_user.get("sub") or current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    updated_user = repo.update_language(user_id, lang)
    return success_response(
        data={"preferred_language": lang},
        message="Language updated successfully",
    )