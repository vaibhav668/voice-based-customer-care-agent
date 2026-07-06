from pydantic import BaseModel


SUPPORTED_LANGUAGES = {"en", "hi", "mr", "te", "ta"}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    language: str = "en"

class ChatResponse(BaseModel):
    session_id: str
    response: str

