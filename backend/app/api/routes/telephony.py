import os
from fastapi import APIRouter, Depends, Form, Request, Header, Response, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.voice.ivr import ivr_manager, IVRState
from app.voice.telephony_provider import TwilioAdapter

router = APIRouter(
    prefix="/api/v1/telephony/twilio",
    tags=["Telephony Call Webhooks"],
)

adapter = TwilioAdapter()


def get_public_audio_url(audio_path: str) -> str:
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    if audio_path.startswith("/"):
        audio_path = audio_path[1:]
    # Remove leading folder reference if PUBLIC_URL hosts static files directly
    # e.g., if generated_audio is mapped as /generated_audio
    return f"{public_url}/{audio_path}"


async def validate_signature_dependency(request: Request, x_twilio_signature: str = Header(None)):
    """Signature validation middleware to verify Twilio request authenticity."""
    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "false").lower() != "true":
        return True
    
    url = str(request.url)
    form_data = await request.form()
    params = {k: v for k, v in form_data.items()}
    if not adapter.validate_signature(url, params, x_twilio_signature):
        raise HTTPException(status_code=400, detail="Invalid Twilio signature.")


@router.post("/incoming")
async def handle_incoming(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Answers inbound telephone calls, sets up caller verification and consent templates."""
    session = ivr_manager.get_or_create_call(CallSid, From, db)
    res = session.advance_state("INIT")
    
    xml = adapter.generate_menu_response(
        prompt=res["prompt"],
        expect_input="DTMF",
        num_digits=1,
        action_url="/api/v1/telephony/twilio/consent",
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/consent")
async def handle_consent(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Processes customer recording consent digit presses."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits or "2")
    
    xml = adapter.generate_menu_response(
        prompt=res["prompt"],
        expect_input="DTMF",
        num_digits=1,
        action_url="/api/v1/telephony/twilio/language",
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/language")
async def handle_language(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Processes preferred language selections."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits or "1")
    
    if session.state == IVRState.ACTIVE_AGENT:
        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        audio_file = await tts.generate(res["prompt"], language=session.language)
        audio_url = get_public_audio_url(audio_file)
        
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["prompt"],
            action_url="/api/v1/telephony/twilio/agent",
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/twilio/verify_code",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/verify_code")
async def handle_verify_code(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Collects and validates 6 digit booking reference code keypad inputs."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits)
    
    if session.state == IVRState.VERIFICATION_PHONE_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=10,
            action_url="/api/v1/telephony/twilio/verify_phone",
        )
    elif session.state == IVRState.ACTIVE_AGENT:
        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        audio_file = await tts.generate(res["prompt"], language=session.language)
        audio_url = get_public_audio_url(audio_file)
        
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["prompt"],
            action_url="/api/v1/telephony/twilio/agent",
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/twilio/verify_code",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/verify_phone")
async def handle_verify_phone(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Enforces unverified caller registered phone numbers two-step check."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits)
    
    if session.state == IVRState.ACTIVE_AGENT:
        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        audio_file = await tts.generate(res["prompt"], language=session.language)
        audio_url = get_public_audio_url(audio_file)
        
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["prompt"],
            action_url="/api/v1/telephony/twilio/agent",
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=10,
            action_url="/api/v1/telephony/twilio/verify_phone",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/agent")
async def handle_agent_turn(
    CallSid: str = Form(...),
    SpeechResult: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Receives and forwards caller spoken responses into NLU understanding loops."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    
    text_input = SpeechResult or "hello"
    res = await session.process_text_agent_turn(text_input)
    
    audio_url = get_public_audio_url(res["audio_path"]) if res.get("audio_path") else ""
    
    if session.state == IVRState.FEEDBACK_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["text"],
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/twilio/feedback",
        )
    else:
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["text"],
            action_url="/api/v1/telephony/twilio/agent",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/feedback")
async def handle_feedback(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Records customer rating keypad entry, broadcasts outcomes to admin sockets, and hangs up."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits)
    
    xml = adapter.generate_completion_response(res["prompt"])
    return Response(content=xml, media_type="application/xml")


@router.post("/status")
async def handle_status_callback(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Receives Twilio status notifications to safely shut down hung up call threads."""
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        session = ivr_manager.get_or_create_call(CallSid, "", db)
        if session.state != IVRState.COMPLETED:
            session.complete_call()
    return {"status": "ok"}
