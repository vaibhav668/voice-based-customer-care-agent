import os
from fastapi import APIRouter, Depends, Form, Request, Header, Response, HTTPException
from sqlalchemy.orm import Session
from plivo import plivoxml

from app.database.session import get_db
from app.voice.ivr import ivr_manager, IVRState
from app.voice.telephony_provider import PlivoAdapter

router = APIRouter(
    prefix="/api/v1/telephony/plivo",
    tags=["Telephony Call Webhooks"],
)

adapter = PlivoAdapter()


def get_public_audio_url(audio_path: str) -> str:
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    if public_url.endswith("/"):
        public_url = public_url[:-1]
    if audio_path.startswith("/"):
        audio_path = audio_path[1:]
    return f"{public_url}/{audio_path}"


async def safe_tts_audio_url(text: str, language: str = "en") -> str:
    """Generates TTS audio and returns its public URL, or empty string on failure.
    
    Returns empty string when TTS fails so callers can fall back to Plivo's
    built-in Speak TTS, avoiding broken Play URLs that cause Invalid Action XML errors.
    """
    try:
        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        audio_file = await tts.generate(text, language=language)
        if not audio_file:
            return ""
        # Resolve path using the TextToSpeech absolute output directory
        filename = audio_file.split("/")[-1]
        full_path = tts.output_dir / filename
        if not full_path.exists():
            print(f"Warning: TTS audio file not found on disk at: {full_path}")
            return ""
        return get_public_audio_url(audio_file)
    except Exception as e:
        print(f"Notice: TTS generation failed, using Speak fallback: {e}")
        return ""


def get_public_url(path: str) -> str:
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    if public_url.endswith("/"):
        public_url = public_url[:-1]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{public_url}{path}"



async def validate_plivo_signature_dependency(
    request: Request,
    x_plivo_signature_v3: str = Header(None, alias="X-Plivo-Signature-V3"),
    x_plivo_signature_v3_nonce: str = Header(None, alias="X-Plivo-Signature-V3-Nonce")
):
    """Signature validation middleware to verify Plivo request authenticity."""
    if os.getenv("PLIVO_VALIDATE_SIGNATURE", "false").lower() != "true":
        return True
    
    url = str(request.url)
    method = request.method
    form_data = await request.form()
    params = {k: v for k, v in form_data.items()}
    
    if not x_plivo_signature_v3 or not x_plivo_signature_v3_nonce:
        raise HTTPException(status_code=400, detail="Missing Plivo signature headers.")
        
    if not adapter.validate_signature(method, url, x_plivo_signature_v3_nonce, x_plivo_signature_v3, params):
        raise HTTPException(status_code=400, detail="Invalid Plivo signature.")


@router.post("/test-outbound")
async def trigger_test_outbound(
    to_phone: str = "+918266894170",
    db: Session = Depends(get_db),
):
    """Triggers an outbound test call to the user's phone, linking it to the IVR loop."""
    auth_id = os.getenv("PLIVO_AUTH_ID")
    auth_token = os.getenv("PLIVO_AUTH_TOKEN")
    from_phone = os.getenv("PLIVO_PHONE_NUMBER")
    public_url = os.getenv("PUBLIC_URL")

    if not all([auth_id, auth_token, from_phone, public_url]):
        raise HTTPException(
            status_code=400,
            detail="Missing required Plivo configuration settings: ID, Token, phone, or PUBLIC_URL."
        )

    try:
        import plivo
        client = plivo.RestClient(auth_id, auth_token)
        call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            answer_url=f"{public_url}/api/v1/telephony/plivo/incoming",
            hangup_url=f"{public_url}/api/v1/telephony/plivo/hangup",
            ring_url=f"{public_url}/api/v1/telephony/plivo/events"
        )
        call_uuid = getattr(call, "call_uuid", None) or (call.get("call_uuid") if hasattr(call, "get") else None)
        return {
            "status": "success",
            "message": f"Outbound call triggered successfully to {to_phone}.",
            "call_uuid": call_uuid
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate outbound Plivo call: {str(e)}"
        )


@router.post("/incoming")
async def handle_incoming(
    request: Request,
    CallUUID: str = Form(...),
    From: str = Form(None),
    To: str = Form(None),
    Direction: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Answers inbound/outbound telephone calls, sets up caller verification and consent templates."""
    plivo_number = os.getenv("PLIVO_PHONE_NUMBER", "").replace("+", "").replace(" ", "")
    
    from_digits = (From or "").replace("+", "").replace(" ", "")
    if plivo_number and from_digits.endswith(plivo_number):
        # This is an outbound call — customer is in 'To'
        caller_phone = To or From
    else:
        caller_phone = From
    
    session = ivr_manager.get_or_create_call(CallUUID, caller_phone, db)
    res = session.advance_state("INIT")
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    xml = adapter.generate_menu_response(
        prompt=res["prompt"],
        expect_input="DTMF",
        num_digits=1,
        action_url="/api/v1/telephony/plivo/language",
        audio_url=audio_url,
        language=session.language,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/consent")
async def handle_consent(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Processes customer recording consent digit presses."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits or "2")
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    if session.state == IVRState.OTP_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/plivo/otp",
            audio_url=audio_url,
            language=session.language,
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/plivo/language",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/otp")
async def handle_otp(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Processes customer OTP inputs."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits)
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    if session.state == IVRState.LANGUAGE_SELECTION_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/plivo/language",
            audio_url=audio_url,
            language=session.language,
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/plivo/otp",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/language")
async def handle_language(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Processes preferred language selections."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits or "1")
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    xml = adapter.generate_menu_response(
        prompt=res["prompt"],
        expect_input="DTMF",
        num_digits=6,
        action_url="/api/v1/telephony/plivo/verify_code",
        audio_url=audio_url,
        language=session.language,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/verify_code")
async def handle_verify_code(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Collects and validates booking reference code keypad inputs."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits)
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    if session.state == IVRState.ACTIVE_AGENT:
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["prompt"],
            action_url="/api/v1/telephony/plivo/agent",
            language=session.language,
        )
    else:

        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/plivo/verify_code",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/verify_phone")
async def handle_verify_phone(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Redirect fallback for verify_phone."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits)
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)
    
    if session.state == IVRState.ACTIVE_AGENT:
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["prompt"],
            action_url="/api/v1/telephony/plivo/agent",
            language=session.language,
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/plivo/verify_code",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/agent")
async def handle_agent_turn(
    CallUUID: str = Form(...),
    Speech: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Receives spoken inputs, feeds them to ChatService, and plays AI response + DTMF choice menu."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    from app.voice.ivr import PROMPTS
    
    choose_prompt = PROMPTS.get(session.language, PROMPTS["en"])["choose_query"]
    
    if not Speech or not Speech.strip():
        audio_url = await safe_tts_audio_url(choose_prompt, language=session.language)

        xml = adapter.generate_query_choice_response(
            audio_url=audio_url,
            text_prompt=choose_prompt,
            action_url="/api/v1/telephony/plivo/query_choice",
            language=session.language,
        )
        return Response(content=xml, media_type="application/xml")

    res = await session.process_text_agent_turn(Speech, append_text=choose_prompt)
    audio_url = get_public_audio_url(res["audio_path"]) if res.get("audio_path") and res.get("audio_path") else ""
    
    xml = adapter.generate_query_choice_response(
        audio_url=audio_url,
        text_prompt=f"{res['text']} {choose_prompt}",
        action_url="/api/v1/telephony/plivo/query_choice",
        language=session.language,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/query_choice")
async def handle_query_choice(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Processes caller continue or end conversation choice."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    from app.voice.ivr import PROMPTS
    
    if Digits == "1":
        speak_prompt = PROMPTS.get(session.language, PROMPTS["en"])["speak_query"]
        
        audio_url = await safe_tts_audio_url(speak_prompt, language=session.language)

        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=speak_prompt,
            action_url="/api/v1/telephony/plivo/agent",
            language=session.language,
        )
    else:
        session.state = IVRState.FEEDBACK_PENDING
        session._save_to_db()
        
        from app.repositories.conversation_repository import ConversationRepository
        conv_repo = ConversationRepository(db)
        conv = conv_repo.get_by_session_id(session.session_id)
        if conv:
            conv.resolution_status = "resolved"
            db.commit()
            
        feedback_prompt = PROMPTS.get(session.language, PROMPTS["en"])["feedback"]
        
        audio_url = await safe_tts_audio_url(feedback_prompt, language=session.language)

        xml = adapter.generate_menu_response(
            prompt=feedback_prompt,
            expect_input="DTMF",
            num_digits=2,
            action_url="/api/v1/telephony/plivo/feedback",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/feedback")
async def handle_feedback(
    Digits: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Records customer rating keypad entry, broadcasts outcomes to admin sockets, and hangs up."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    res = session.advance_state("DTMF", Digits)
    
    audio_url = await safe_tts_audio_url(res["prompt"], language=session.language)

    xml = adapter.generate_completion_response(
        prompt=res["prompt"],
        language=session.language,
        audio_url=audio_url,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/hangup")
async def handle_hangup(
    CallUUID: str = Form(...),
    HangupCause: str = Form(None),
    HangupSource: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Receives Plivo hangup status notification to safely shut down hung up call threads."""
    print(f"[{CallUUID}] Hangup webhook received. Cause: {HangupCause}, Source: {HangupSource}")
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    if session.state != IVRState.COMPLETED:
        session.complete_call()
    return {"status": "ok"}


@router.post("/events")
async def handle_events(
    CallUUID: str = Form(...),
    CallStatus: str = Form(None),
    Event: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Receives Plivo general call progression events."""
    import logging
    logging.getLogger(__name__).info(f"Received Plivo Event: {Event}, Status: {CallStatus} for CallUUID: {CallUUID}")
    return {"status": "ok"}


@router.post("/recording-callback")
async def handle_recording_callback(
    RecordingUrl: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
):
    """Processes Plivo recording callback and links the completed recording URL to the conversation record."""
    from app.database.models.ivr_session import IvrSession
    from app.database.models.conversation import Conversation
    from app.voice.ivr import broadcast_call_event

    ivr_sess = db.query(IvrSession).filter_by(call_id=CallUUID).first()
    if not ivr_sess:
        return {"status": "ignored", "reason": "No IVR session found for CallUUID"}
        
    if RecordingUrl:
        conv = db.query(Conversation).filter_by(session_id=ivr_sess.session_id).first()
        if conv:
            conv.recording_url = RecordingUrl
            db.commit()
            broadcast_call_event("call_updated", ivr_sess.session_id, "Call recording is now available.", {
                "recording_url": RecordingUrl
            })
            return {"status": "success", "message": "Recording URL mapped to conversation."}
            
    return {"status": "ignored"}
