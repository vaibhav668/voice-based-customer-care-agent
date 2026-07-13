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
    From: str = Form(None),
    To: str = Form(None),
    Direction: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Answers inbound/outbound telephone calls, sets up caller verification and consent templates."""
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER", "").replace("+", "").replace(" ", "")
    
    # For outbound calls: From = Twilio number, To = customer number
    # For inbound calls:  From = customer number, To = Twilio number
    from_digits = (From or "").replace("+", "").replace(" ", "")
    if twilio_number and from_digits.endswith(twilio_number):
        # This is an outbound call — customer is in 'To'
        caller_phone = To or From
    else:
        caller_phone = From
    
    session = ivr_manager.get_or_create_call(CallSid, caller_phone, db)
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
    
    if session.state == IVRState.OTP_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/twilio/otp",
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/twilio/language",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/otp")
async def handle_otp(
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Processes customer OTP inputs."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    res = session.advance_state("DTMF", Digits)
    
    if session.state == IVRState.LANGUAGE_SELECTION_PENDING:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=1,
            action_url="/api/v1/telephony/twilio/language",
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=6,
            action_url="/api/v1/telephony/twilio/otp",
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
    """Collects and validates booking reference code keypad inputs."""
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
    """Redirect fallback for verify_phone."""
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
            num_digits=6,
            action_url="/api/v1/telephony/twilio/verify_code",
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/agent")
async def handle_agent_turn(
    CallSid: str = Form(...),
    SpeechResult: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Receives spoken inputs, feeds them to ChatService, and plays AI response + DTMF choice menu."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    from app.voice.ivr import PROMPTS
    
    if not SpeechResult or not SpeechResult.strip():
        choose_prompt = PROMPTS.get(session.language, PROMPTS["en"])["choose_query"]
        xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
        xml += f'    <Gather action="/api/v1/telephony/twilio/query_choice" method="POST" input="dtmf" numDigits="1" timeout="4">\n'
        xml += f'        <Say>{choose_prompt}</Say>\n'
        xml += f'    </Gather>\n'
        xml += f'    <Redirect method="POST">/api/v1/telephony/twilio/query_choice?timeout=1</Redirect>\n'
        xml += f'</Response>'
        return Response(content=xml, media_type="application/xml")

    res = await session.process_text_agent_turn(SpeechResult)
    audio_url = get_public_audio_url(res["audio_path"]) if res.get("audio_path") else ""
    choose_prompt = PROMPTS.get(session.language, PROMPTS["en"])["choose_query"]
    
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
    xml += f'    <Gather action="/api/v1/telephony/twilio/query_choice" method="POST" input="dtmf" numDigits="1" timeout="4">\n'
    if audio_url:
        xml += f'        <Play>{audio_url}</Play>\n'
    else:
        xml += f'        <Say>{res["text"]}</Say>\n'
    xml += f'        <Say>{choose_prompt}</Say>\n'
    xml += f'    </Gather>\n'
    xml += f'    <Redirect method="POST">/api/v1/telephony/twilio/query_choice?timeout=1</Redirect>\n'
    xml += f'</Response>'
    return Response(content=xml, media_type="application/xml")


@router.post("/query_choice")
async def handle_query_choice(
    request: Request,
    Digits: str = Form(None),
    CallSid: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_signature_dependency),
):
    """Processes caller continue or end conversation choice."""
    session = ivr_manager.get_or_create_call(CallSid, "", db)
    from app.voice.ivr import PROMPTS
    
    if Digits == "1":
        speak_prompt = PROMPTS.get(session.language, PROMPTS["en"])["speak_query"]
        xml = adapter.generate_voice_agent_response(
            audio_url="",
            text_prompt=speak_prompt,
            action_url="/api/v1/telephony/twilio/agent",
        )
    elif Digits == "0":
        session.state = IVRState.FEEDBACK_PENDING
        session._save_to_db()
        
        from app.repositories.conversation_repository import ConversationRepository
        conv_repo = ConversationRepository(db)
        conv = conv_repo.get_by_session_id(session.session_id)
        if conv:
            conv.resolution_status = "resolved"
            db.commit()
            
        feedback_prompt = PROMPTS.get(session.language, PROMPTS["en"])["feedback"]
        xml = adapter.generate_menu_response(
            prompt=feedback_prompt,
            expect_input="DTMF",
            num_digits=2,
            action_url="/api/v1/telephony/twilio/feedback",
        )
    else:
        is_timeout_retry = request.query_params.get("timeout") == "1"
        if not is_timeout_retry:
            reminder_prompt = PROMPTS.get(session.language, PROMPTS["en"])["timeout_reminder"]
            xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
            xml += f'    <Gather action="/api/v1/telephony/twilio/query_choice" method="POST" input="dtmf" numDigits="1" timeout="4">\n'
            xml += f'        <Say>{reminder_prompt}</Say>\n'
            xml += f'    </Gather>\n'
            xml += f'    <Redirect method="POST">/api/v1/telephony/twilio/query_choice?timeout=1</Redirect>\n'
            xml += f'</Response>'
        else:
            session.state = IVRState.FEEDBACK_PENDING
            session._save_to_db()
            
            feedback_prompt = PROMPTS.get(session.language, PROMPTS["en"])["feedback"]
            xml = adapter.generate_menu_response(
                prompt=feedback_prompt,
                expect_input="DTMF",
                num_digits=2,
                action_url="/api/v1/telephony/twilio/feedback",
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


@router.post("/recording-callback")
async def handle_recording_callback(
    RecordingUrl: str = Form(None),
    CallSid: str = Form(...),
    RecordingStatus: str = Form(None),
    db: Session = Depends(get_db),
):
    """Processes Twilio recording callback and links the completed recording URL to the conversation record."""
    from app.database.models.ivr_session import IvrSession
    from app.database.models.conversation import Conversation
    from app.voice.ivr import broadcast_call_event

    ivr_sess = db.query(IvrSession).filter_by(call_id=CallSid).first()
    if not ivr_sess:
        return {"status": "ignored", "reason": "No IVR session found for CallSid"}
        
    if RecordingStatus == "completed" and RecordingUrl:
        conv = db.query(Conversation).filter_by(session_id=ivr_sess.session_id).first()
        if conv:
            conv.recording_url = RecordingUrl
            db.commit()
            broadcast_call_event("call_updated", ivr_sess.session_id, "Call recording is now available.", {
                "recording_url": RecordingUrl
            })
            return {"status": "success", "message": "Recording URL mapped to conversation."}
            
    return {"status": "ignored", "RecordingStatus": RecordingStatus}
