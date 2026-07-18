from fastapi import APIRouter, Depends, Form, Request, Header, Response, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from plivo import plivoxml
import os
import asyncio
import base64
import struct
import math
import json
import wave
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.database.session import SessionLocal

from app.database.session import get_db
from app.voice.ivr import ivr_manager, IVRState
from app.voice.telephony_provider import PlivoAdapter

router = APIRouter(
    prefix="/api/v1/telephony/plivo",
    tags=["Telephony Call Webhooks"],
)

adapter = PlivoAdapter()
BOOKING_REF_DIGITS = 4


def get_public_audio_url(audio_path: str) -> str:
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    if public_url.endswith("/"):
        public_url = public_url[:-1]
    if audio_path.startswith("/"):
        audio_path = audio_path[1:]
    return f"{public_url}/{audio_path}"


async def safe_tts_audio_url(text: str, language: str = "en") -> str:
    """Generates high-quality polite neural audio using edge-tts (hi-IN-SwaraNeural for Hindi)
    and returns absolute public URL for Plivo <Play> playback.
    """
    if not text or not text.strip():
        return ""
    try:
        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        audio_path = await tts.generate(text, language=language)
        return get_public_audio_url(audio_path)
    except Exception as e:
        print("Notice: Dynamic TTS audio generation fallback:", e)
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
        num_digits=BOOKING_REF_DIGITS,
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
        public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
        if public_url.startswith("https://"):
            ws_url = public_url.replace("https://", "wss://")
        else:
            ws_url = public_url.replace("http://", "ws://")
        if ws_url.endswith("/"):
            ws_url = ws_url[:-1]
        ws_url = f"{ws_url}/api/v1/telephony/plivo/stream?call_uuid={CallUUID}"

        xml = adapter.generate_stream_response(
            stream_url=ws_url,
            keep_call_alive=True,
            call_uuid=CallUUID
        )
    else:

        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=BOOKING_REF_DIGITS,
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
        public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
        if public_url.startswith("https://"):
            ws_url = public_url.replace("https://", "wss://")
        else:
            ws_url = public_url.replace("http://", "ws://")
        if ws_url.endswith("/"):
            ws_url = ws_url[:-1]
        ws_url = f"{ws_url}/api/v1/telephony/plivo/stream?call_uuid={CallUUID}"

        xml = adapter.generate_stream_response(
            stream_url=ws_url,
            keep_call_alive=True,
            call_uuid=CallUUID
        )
    else:
        xml = adapter.generate_menu_response(
            prompt=res["prompt"],
            expect_input="DTMF",
            num_digits=BOOKING_REF_DIGITS,
            action_url="/api/v1/telephony/plivo/verify_code",
            audio_url=audio_url,
            language=session.language,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/agent")
async def handle_agent_turn(
    CallUUID: str = Form(...),
    Speech: str = Form(None),
    SpeechResult: str = Form(None),
    RecordUrl: str = Form(None),
    RecordingUrl: str = Form(None),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Receives spoken inputs or recordings, feeds them to ChatService, and plays AI response + DTMF choice menu."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    from app.voice.ivr import PROMPTS
    
    choose_prompt = PROMPTS.get(session.language, PROMPTS["en"])["choose_query"]
    record_url = RecordUrl or RecordingUrl
    user_speech = Speech or SpeechResult
    
    res = None

    # Option A: Spoken Audio Recording processing (primary for non-English regional flow)
    if record_url:
        import httpx
        from pathlib import Path
        import uuid
        
        TEMP_DIR = Path(__file__).parent.parent.parent.parent / "temp"
        TEMP_DIR.mkdir(exist_ok=True)
        
        extension = ".mp3"
        filename = f"{uuid.uuid4()}{extension}"
        file_path = TEMP_DIR / filename
        relative_audio_path = f"temp/{filename}"
        
        try:
            auth_id = os.getenv("PLIVO_AUTH_ID")
            auth_token = os.getenv("PLIVO_AUTH_TOKEN")
            auth = (auth_id, auth_token) if auth_id and auth_token else None

            async with httpx.AsyncClient(follow_redirects=True) as http_client:
                response = await http_client.get(record_url, auth=auth)
                if response.status_code != 200 and auth:
                    # Fall back to unauthenticated fetch in case of external presigned URL
                    response = await http_client.get(record_url)
                
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                else:
                    raise Exception(f"Failed to download audio: status {response.status_code}")
            
            res = await session.process_voice_agent_turn(
                audio_path=str(file_path),
                audio_relative_path=relative_audio_path,
                append_text=choose_prompt
            )
        except Exception as e:
            print("Notice: Failed to download or process Plivo recording:", e)
            res = None

    # Option B: Direct Speech / ASR processing (if recording unavailable or failed)
    if not res and user_speech and user_speech.strip():
        try:
            res = await session.process_text_agent_turn(user_speech, append_text=choose_prompt)
        except Exception as e:
            print("Notice: Failed to process text agent turn:", e)
            res = None

    # If neither input mode produced a response, prompt caller to choose/re-speak
    if not res:
        audio_url = await safe_tts_audio_url(choose_prompt, language=session.language)
        xml = adapter.generate_query_choice_response(
            audio_url=audio_url,
            text_prompt=choose_prompt,
            action_url="/api/v1/telephony/plivo/query_choice",
            language=session.language,
        )
        return Response(content=xml, media_type="application/xml")

    # Safe audio URL resolution if TTS audio was generated
    audio_url = ""
    raw_path = res.get("audio_path", "")
    if not raw_path and res.get("text"):
        audio_url = await safe_tts_audio_url(f"{res['text']} {choose_prompt}", language=session.language)
    elif raw_path:
        try:
            from app.voice.tts import TextToSpeech
            tts_svc = TextToSpeech()
            filename = raw_path.split("/")[-1]
            full_path = tts_svc.output_dir / filename
            if full_path.exists():
                audio_url = get_public_audio_url(raw_path)
        except Exception as ex:
            print(f"Notice: Audio path resolve failed: {ex}")
            
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
    Speech: str = Form(None),
    SpeechResult: str = Form(None),
    RecordUrl: str = Form(None),
    RecordingUrl: str = Form(None),
    CallUUID: str = Form(...),
    db: Session = Depends(get_db),
    _ = Depends(validate_plivo_signature_dependency),
):
    """Processes caller continue or end conversation choice, or directly processes spoken query/recording."""
    session = ivr_manager.get_or_create_call(CallUUID, "", db)
    from app.voice.ivr import PROMPTS
    
    user_speech = Speech or SpeechResult
    record_url = RecordUrl or RecordingUrl
    
    from app.conversation.manager import ConversationManager
    conv_manager = ConversationManager()
    mem_session = conv_manager.get_session(session.session_id)
    choose_prompt = PROMPTS.get(session.language, PROMPTS["en"])["choose_query"]

    if Digits == "1":
        mem_session.entities["query_choice_timeouts"] = 0
        speak_prompt = PROMPTS.get(session.language, PROMPTS["en"])["speak_query"]
        audio_url = await safe_tts_audio_url(speak_prompt, language=session.language)
        xml = adapter.generate_voice_agent_response(
            audio_url=audio_url,
            text_prompt=speak_prompt,
            action_url="/api/v1/telephony/plivo/agent",
            language=session.language,
        )
    elif record_url:
        mem_session.entities["query_choice_timeouts"] = 0
        import httpx
        from pathlib import Path
        import uuid
        
        TEMP_DIR = Path(__file__).parent.parent.parent.parent / "temp"
        TEMP_DIR.mkdir(exist_ok=True)
        
        filename = f"{uuid.uuid4()}.mp3"
        file_path = TEMP_DIR / filename
        relative_audio_path = f"temp/{filename}"
        
        res = None
        try:
            auth_id = os.getenv("PLIVO_AUTH_ID")
            auth_token = os.getenv("PLIVO_AUTH_TOKEN")
            auth = (auth_id, auth_token) if auth_id and auth_token else None
            
            async with httpx.AsyncClient(follow_redirects=True) as http_client:
                response = await http_client.get(record_url, auth=auth)
                if response.status_code != 200 and auth:
                    response = await http_client.get(record_url)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                else:
                    raise Exception(f"Failed to download audio: status {response.status_code}")
                    
            res = await session.process_voice_agent_turn(
                audio_path=str(file_path),
                audio_relative_path=relative_audio_path,
                append_text=choose_prompt
            )
        except Exception as e:
            print("Notice: Failed to download or process Plivo recording in query_choice:", e)
            res = None

        if res:
            audio_url = ""
            raw_path = res.get("audio_path", "")
            if raw_path:
                try:
                    from app.voice.tts import TextToSpeech
                    tts_svc = TextToSpeech()
                    filename = raw_path.split("/")[-1]
                    full_path = tts_svc.output_dir / filename
                    if full_path.exists():
                        audio_url = get_public_audio_url(raw_path)
                except Exception:
                    pass
            xml = adapter.generate_query_choice_response(
                audio_url=audio_url,
                text_prompt=f"{res['text']} {choose_prompt}",
                action_url="/api/v1/telephony/plivo/query_choice",
                language=session.language,
            )
        else:
            audio_url = await safe_tts_audio_url(choose_prompt, language=session.language)
            xml = adapter.generate_query_choice_response(
                audio_url=audio_url,
                text_prompt=choose_prompt,
                action_url="/api/v1/telephony/plivo/query_choice",
                language=session.language,
            )
    elif user_speech and user_speech.strip():
        mem_session.entities["query_choice_timeouts"] = 0
        # User directly spoke their next query! Process it.
        res = await session.process_text_agent_turn(user_speech, append_text=choose_prompt)
        audio_url = ""
        raw_path = res.get("audio_path", "")
        if raw_path:
            try:
                from app.voice.tts import TextToSpeech
                tts_svc = TextToSpeech()
                filename = raw_path.split("/")[-1]
                full_path = tts_svc.output_dir / filename
                if full_path.exists():
                    audio_url = get_public_audio_url(raw_path)
            except Exception:
                pass
        xml = adapter.generate_query_choice_response(
            audio_url=audio_url,
            text_prompt=f"{res['text']} {choose_prompt}",
            action_url="/api/v1/telephony/plivo/query_choice",
            language=session.language,
        )
    elif Digits == "0":
        mem_session.entities["query_choice_timeouts"] = 0
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
    else:
        # Silence/Timeout (no DTMF or speech input)
        timeouts = mem_session.entities.get("query_choice_timeouts", 0)
        if timeouts < 1:
            mem_session.entities["query_choice_timeouts"] = timeouts + 1
            timeout_prompt = PROMPTS.get(session.language, PROMPTS["en"])["timeout_reminder"]
            audio_url = await safe_tts_audio_url(timeout_prompt, language=session.language)
            xml = adapter.generate_query_choice_response(
                audio_url=audio_url,
                text_prompt=timeout_prompt,
                action_url="/api/v1/telephony/plivo/query_choice",
                language=session.language,
            )
        else:
            # Second timeout: gracefully finalize and transfer to feedback
            mem_session.entities["query_choice_timeouts"] = 0
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


BIAS = 0x84
CLIP = 32635

def pcm16_to_ulaw(sample: int) -> int:
    """Encodes a signed 16-bit PCM integer sample to an 8-bit G.711 mu-law byte."""
    sign = (sample >> 8) & 0x80
    if sample < 0:
        sample = -sample
        sign = 0x80
    else:
        sign = 0x00

    if sample > CLIP:
        sample = CLIP

    sample += BIAS
    exponent = 7
    mask = 0x4000
    while (sample & mask) == 0 and exponent > 0:
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    ulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return ulaw_byte


def get_mulaw_rms(mulaw_data: bytes) -> float:
    """Computes the RMS energy of a chunk of G.711 mu-law bytes for silence detection."""
    if not mulaw_data:
        return 0.0
    sum_squares = 0
    for b in mulaw_data:
        u_val = ~b & 0xFF
        sign = (u_val & 0x80)
        exponent = (u_val & 0x70) >> 4
        mantissa = u_val & 0x0F
        sample = (mantissa << 3) + 33
        sample <<= exponent
        sample -= 33
        pcm_val = -sample if sign else sample
        sum_squares += pcm_val * pcm_val
    return math.sqrt(sum_squares / len(mulaw_data))


@router.websocket("/stream")
async def handle_websocket_stream(websocket: WebSocket):
    await websocket.accept()
    
    db = SessionLocal()
    chat_service = ChatService(db)
    
    stream_id = None
    call_uuid = websocket.query_params.get("call_uuid")
    session = None
    if call_uuid:
        session = ivr_manager.get_or_create_call(call_uuid, "", db)
    
    caller_audio_buffer = bytearray()
    
    is_speaking = False
    silence_counter = 0
    SILENCE_THRESHOLD_PACKETS = 40  # ~800ms at 20ms chunks
    RMS_SILENCE_LIMIT = 400.0
    
    tts_queue = asyncio.Queue()
    stop_playback_flag = asyncio.Event()
    playback_task = None
    
    async def stream_sentence_audio(sentence: str):
        try:
            from app.voice.tts import TextToSpeech
            tts = TextToSpeech()
            
            # Generate TTS audio (MP3)
            audio_path = await tts.generate(sentence, language=session.language if session else "en")
            full_path = str(tts.output_dir.parent / audio_path)

            # Use ffmpeg to decode MP3 → raw 8kHz mono signed 16-bit PCM (no temp files needed)
            import subprocess
            ffmpeg_proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y",
                "-i", full_path,
                "-ar", "8000",        # resample to 8kHz
                "-ac", "1",           # mono
                "-f", "s16le",        # raw signed 16-bit little-endian PCM
                "-",                  # output to stdout
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            pcm16_data, _ = await ffmpeg_proc.communicate()

            num_samples = len(pcm16_data) // 2
            samples = struct.unpack(f"<{num_samples}h", pcm16_data)

            mulaw_bytes = bytearray(len(samples))
            for idx, s in enumerate(samples):
                mulaw_bytes[idx] = pcm16_to_ulaw(s)
                
            chunk_size = 320  # 40ms of audio at 8000Hz µ-law
            for offset in range(0, len(mulaw_bytes), chunk_size):
                if stop_playback_flag.is_set():
                    break
                chunk = mulaw_bytes[offset:offset+chunk_size]
                payload = base64.b64encode(chunk).decode("utf-8")
                
                await websocket.send_json({
                    "event": "playAudio",
                    "media": {
                        "contentType": "audio/x-mulaw",
                        "sampleRate": "8000",
                        "payload": payload
                    }
                })
                await asyncio.sleep(0.04)
        except Exception as e:
            print(f"Error in stream_sentence_audio: {e}")


    async def playback_worker():
        try:
            while True:
                sentence = await tts_queue.get()
                if sentence is None:
                    break
                
                if not stop_playback_flag.is_set():
                    await stream_sentence_audio(sentence)
                tts_queue.task_done()
        except asyncio.CancelledError:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            event = msg.get("event")
            
            if event == "start":
                meta = msg.get("start", {})
                # Plivo sends callId (not callUuid) inside the start sub-object
                stream_id = meta.get("streamId") or msg.get("streamId")
                if not call_uuid:
                    # Primary: start.callId (Plivo's documented field name)
                    call_uuid = (
                        meta.get("callId")
                        or meta.get("callUuid")
                        or meta.get("call_uuid")
                        or msg.get("callId")
                        or msg.get("callUuid")
                    )
                    # Fallback: parse from extra_headers if injected by Stream XML
                    if not call_uuid:
                        extra_headers = msg.get("extra_headers", "")
                        for part in str(extra_headers).split(";"):
                            if part.strip().startswith("call_uuid="):
                                call_uuid = part.strip().split("=", 1)[1]
                                break
                print(f"[WebSocket Stream] Started for Call UUID: {call_uuid}, Stream ID: {stream_id}")
                print(f"[WebSocket Stream] Full start payload: {json.dumps(msg)[:500]}")
                
                if not session and call_uuid:
                    session = ivr_manager.get_or_create_call(call_uuid, "", db)
                if session:
                    from app.voice.ivr import PROMPTS
                    lang_prompts = PROMPTS.get(session.language, PROMPTS["en"])
                    prompt = lang_prompts.get("speak_query", "Please speak your query now.")
                    
                    stop_playback_flag.clear()
                    playback_task = asyncio.create_task(playback_worker())
                    await tts_queue.put(prompt)
                else:
                    print(f"[WebSocket Stream] WARNING: No session found for call_uuid={call_uuid}. Cannot greet caller.")
                
            elif event == "media":
                media = msg.get("media", {})
                payload_b64 = media.get("payload")
                if not payload_b64:
                    continue
                
                payload = base64.b64decode(payload_b64)
                rms = get_mulaw_rms(payload)
                
                if rms > RMS_SILENCE_LIMIT:
                    silence_counter = 0
                    if not is_speaking:
                        is_speaking = True
                        print("[VAD] Caller speaking detected.")
                        stop_playback_flag.set()
                        if stream_id:
                            await websocket.send_json({
                                "event": "clearAudio",
                                "streamId": stream_id
                            })
                        while not tts_queue.empty():
                            try:
                                tts_queue.get_nowait()
                                tts_queue.task_done()
                            except asyncio.QueueEmpty:
                                break
                    caller_audio_buffer.extend(payload)
                else:
                    if is_speaking:
                        silence_counter += 1
                        caller_audio_buffer.extend(payload)
                        
                        if silence_counter >= SILENCE_THRESHOLD_PACKETS:
                            print("[VAD] Caller silence detected. Processing query...")
                            is_speaking = False
                            silence_counter = 0
                            
                            audio_data = bytes(caller_audio_buffer)
                            caller_audio_buffer.clear()
                            
                            if len(audio_data) >= 12000:
                                import tempfile
                                temp_raw = tempfile.NamedTemporaryFile(suffix=".raw", delete=False)
                                temp_raw.write(audio_data)
                                temp_raw_path = temp_raw.name
                                temp_raw.close()
                                
                                temp_wav_16k = tempfile.NamedTemporaryFile(suffix="_16k.wav", delete=False)
                                temp_wav_16k_path = temp_wav_16k.name
                                temp_wav_16k.close()
                                
                                stt_input_path = None
                                try:
                                    # FFMPEG decodes raw 8kHz G.711 mu-law directly and resamples to crisp 16kHz mono WAV
                                    upsample_proc = await asyncio.create_subprocess_exec(
                                        "ffmpeg", "-y",
                                        "-f", "mulaw",
                                        "-ar", "8000",
                                        "-ac", "1",
                                        "-i", temp_raw_path,
                                        "-ar", "16000",
                                        "-ac", "1",
                                        temp_wav_16k_path,
                                        stdout=asyncio.subprocess.DEVNULL,
                                        stderr=asyncio.subprocess.DEVNULL,
                                    )
                                    await upsample_proc.wait()
                                    stt_input_path = temp_wav_16k_path
                                except Exception as ex:
                                    print(f"[WebSocket Stream] FFMPEG conversion error: {ex}")
                                
                                if stt_input_path and os.path.exists(stt_input_path):
                                    try:
                                        from app.voice.stt import SpeechToText
                                        stt = SpeechToText()
                                        transcription = stt.transcribe(stt_input_path, language=session.language if session else "en")
                                        print(f"[WebSocket Stream] Transcribed user query: {transcription}")
                                        
                                        if transcription.strip():
                                            if playback_task and not playback_task.done():
                                                playback_task.cancel()
                                            stop_playback_flag.clear()
                                            playback_task = asyncio.create_task(playback_worker())
                                            
                                            chat_req = ChatRequest(
                                                message=transcription,
                                                session_id=session.session_id if session else None,
                                                language=session.language if session else "en"
                                            )
                                            
                                            sentence_accum = ""
                                            async for token in chat_service.process_stream(
                                                request=chat_req,
                                                user_id=session.user_id if session else None,
                                                channel="TELEPHONY",
                                                audio_input_path=stt_input_path
                                            ):
                                                sentence_accum += token
                                                if any(sentence_accum.endswith(p) for p in (".", "?", "!", "\n", "।", "॥")):
                                                    sentence = sentence_accum.strip()
                                                    if sentence:
                                                        await tts_queue.put(sentence)
                                                    sentence_accum = ""
                                                    
                                            if sentence_accum.strip():
                                                await tts_queue.put(sentence_accum.strip())
                                                
                                    except Exception as err:
                                        print(f"Error executing agent stream: {err}")
                                    finally:
                                        for f in [temp_raw_path, temp_wav_16k_path]:
                                            try:
                                                os.remove(f)
                                            except Exception:
                                                pass

            elif event == "stop":
                print(f"[WebSocket Stream] Stop event for Call UUID: {call_uuid}")
                break
    except WebSocketDisconnect:
        print(f"[WebSocket Stream] Disconnected for Call UUID: {call_uuid}")
    except Exception as e:
        print(f"[WebSocket Stream] WebSocket Error: {e}")
    finally:
        if playback_task and not playback_task.done():
            playback_task.cancel()
        db.close()
