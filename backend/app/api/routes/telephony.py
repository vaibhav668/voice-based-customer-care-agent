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


@router.post("/test-outbound")
async def trigger_test_outbound(
    to_phone: str = "+918266894170",
    db: Session = Depends(get_db),
):
    """Triggers an outbound test call to the user's phone, linking it to the IVR loop."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    public_url = os.getenv("PUBLIC_URL")

    if not all([account_sid, auth_token, from_phone, public_url]):
        raise HTTPException(
            status_code=400,
            detail="Missing required Twilio configuration settings: SID, Token, phone, or PUBLIC_URL."
        )

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            url=f"{public_url}/api/v1/telephony/twilio/incoming"
        )
        return {
            "status": "success",
            "message": f"Outbound call triggered successfully to {to_phone}.",
            "call_sid": call.sid
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate outbound Twilio call: {str(e)}"
        )


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
    
    if not SpeechResult or not SpeechResult.strip():
        xml = adapter.generate_menu_response(
            prompt="If you want to ask another query, press 1. If your query is resolved, press 0.",
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/twilio/query_choice",
        )
        return Response(content=xml, media_type="application/xml")

    res = await session.process_text_agent_turn(SpeechResult)
    
    audio_url = get_public_audio_url(res["audio_path"]) if res.get("audio_path") else ""
    
    if session.state == IVRState.FEEDBACK_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["text"],
            expect_input="DTMF",
            num_digits=2,
            action_url="/api/v1/telephony/twilio/feedback",
        )
    else:
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=res["text"],
            action_url="/api/v1/telephony/twilio/agent",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/query_choice")
async def handle_query_choice(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Processes customer selection to continue conversation or trigger CSAT survey."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    
    if Digits == "0":
        session.state = IVRState.FEEDBACK_PENDING
        session._save_to_db()
        
        from app.repositories.conversation_repository import ConversationRepository
        conv_repo = ConversationRepository(db)
        conv = conv_repo.get_by_session_id(session.session_id)
        if conv:
            conv.resolution_status = "resolved"
            db.commit()
            
        feedback_prompt = "Thank you. Please rate your support experience from 1 to 10 using your telephone keypad, where 0 represents a rating of 10."
        if session.language == "hi":
            feedback_prompt = "धन्यवाद। कृपया अपने सहायता अनुभव को 1 से 10 के पैमाने पर रेट करें, जहाँ 0 का अर्थ 10 है।"
        elif session.language == "te":
            feedback_prompt = "ధన్యవాదాలు. దయచేసి మీ టెలిఫోన్ కీప్యాడ్ ఉపయోగించి మీ సహాయ అనుభవాన్ని 1 నుండి 10 వరకు రేట్ చేయండి, ఇక్కడ 0 అంటే 10."
            
        xml = adapter.generate_menu_response(
            prompt=feedback_prompt,
            expect_input="DTMF",
            num_digits=2,
            action_url="/api/v1/telephony/twilio/feedback",
        )
    else:
        xml = adapter.generate_voice_agent_response(
            audio_url="",
            text_prompt="Please speak your query now.",
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
