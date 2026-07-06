from pydantic import BaseModel


class VoiceResponse(BaseModel):
    session_id: str
    text: str
    audio_url: str