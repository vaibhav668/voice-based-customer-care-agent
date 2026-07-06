from fastapi import APIRouter, Depends

from app.auth.dependencies import get_optional_current_user
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)

chat_service = ChatService()


@router.post("/")
def chat(
    request: ChatRequest,
    current_user=Depends(get_optional_current_user),
):
    user_id = current_user.get("sub") or current_user.get("id") if current_user else None
    return chat_service.process(request, user_id=user_id)