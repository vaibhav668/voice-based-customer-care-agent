from pathlib import Path
import uuid

from fastapi import APIRouter, File, Form, UploadFile, Depends

from app.auth.dependencies import get_optional_current_user
from app.voice.service import VoiceService

from sqlalchemy.orm import Session
from app.database.session import get_db

router = APIRouter(
    prefix="/voice",
    tags=["Voice"],
)

TEMP_DIR = Path(__file__).parent.parent.parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)


@router.post("/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):

    extension = Path(audio.filename).suffix
    filename = f"{uuid.uuid4()}{extension}"
    file_path = TEMP_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await audio.read())

    # Store relative path in DB so frontend can build URL correctly
    relative_audio_path = f"temp/{filename}"

    user_id = current_user.get("sub") or current_user.get("id") if current_user else None

    service = VoiceService(db=db)
    return await service.process(
        audio_path=str(file_path),
        audio_relative_path=relative_audio_path,
        session_id=session_id,
        language=language,
        user_id=user_id,
        db=db,
    )