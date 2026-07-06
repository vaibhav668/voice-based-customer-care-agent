from fastapi import APIRouter, Depends

from app.auth.dependencies import get_optional_current_user
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

from sqlalchemy.orm import Session
from app.database.session import get_db

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)


@router.post("")
@router.post("/")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    service = ChatService(db=db)
    return service.process(request, user_id=user_id)