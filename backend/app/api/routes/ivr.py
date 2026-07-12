from pathlib import Path
import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.voice.ivr import ivr_manager, IVRState

router = APIRouter(
    prefix="/api/v1/ivr",
    tags=["IVR Telephony"],
)

TEMP_DIR = Path(__file__).parent.parent.parent.parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)


@router.post("/calls")
def initiate_call(
    call_id: str = Form(...),
    phone_number: str = Form(...),
    db: Session = Depends(get_db),
):
    """Initiates an abstract IVR Call session."""
    session = ivr_manager.get_or_create_call(call_id, phone_number, db)
    # Trigger first transition out of INCOMING
    res = session.advance_state("INIT")
    return {
        "call_id": call_id,
        "phone_number": phone_number,
        **res,
    }


@router.post("/calls/{call_id}/dtmf")
def process_dtmf(
    call_id: str,
    dtmf: str = Form(...),
    db: Session = Depends(get_db),
):
    """Receives DTMF digits and transitions call state."""
    if call_id not in ivr_manager.calls:
        # Load from DB fallback
        session = ivr_manager.get_or_create_call(call_id, "", db)
    else:
        session = ivr_manager.calls[call_id]
    
    res = session.advance_state("DTMF", dtmf)
    return {
        "call_id": call_id,
        **res,
    }


@router.post("/calls/{call_id}/voice")
async def process_voice(
    call_id: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Receives audio voice input, processes it, and returns the next voice agent reply."""
    if call_id not in ivr_manager.calls:
        # Load from DB fallback
        session = ivr_manager.get_or_create_call(call_id, "", db)
    else:
        session = ivr_manager.calls[call_id]
        
    if session.state != IVRState.ACTIVE_AGENT:
        raise HTTPException(status_code=400, detail="Call is not in the active voice agent phase.")

    # Save audio upload
    extension = Path(audio.filename).suffix or ".wav"
    filename = f"ivr-{uuid.uuid4()}{extension}"
    file_path = TEMP_DIR / filename

    with open(file_path, "wb") as f:
        f.write(await audio.read())

    relative_audio_path = f"temp/{filename}"

    try:
        res = await session.process_voice_agent_turn(
            audio_path=str(file_path),
            audio_relative_path=relative_audio_path,
        )
        return {
            "call_id": call_id,
            "state": session.state.value,
            "transcript": res.get("transcript"),
            "prompt": res.get("text"),
            "audio_path": res.get("audio_path"),
            "expect_input": "VOICE",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice agent process error: {str(e)}")


@router.post("/calls/{call_id}/disconnect")
def disconnect_call(
    call_id: str,
    db: Session = Depends(get_db),
):
    """Gracefully terminates an active call session."""
    if call_id not in ivr_manager.calls:
        # Load from DB fallback
        session = ivr_manager.get_or_create_call(call_id, "", db)
    else:
        session = ivr_manager.calls[call_id]

    res = session.complete_call()
    return res
