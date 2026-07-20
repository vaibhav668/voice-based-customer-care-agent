from pathlib import Path
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
from app.utils.latency import LatencyTracker

from app.database.session import get_db
from app.voice.ivr import ivr_manager, IVRState, broadcast_call_event
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
    
    from collections import deque
    import time

    caller_audio_buffer = bytearray()
    pre_roll_buffer = deque(maxlen=25)  # 25 packets = 500ms of pre-speech audio lead-in
    
    is_speaking = False
    silence_counter = 0
    speech_packet_count = 0
    SILENCE_THRESHOLD_PACKETS = 35  # ~700ms at 20ms chunks to allow natural speech pauses
    RMS_SPEECH_THRESHOLD = 480.0    # Raised from 350 → 480: phone echo/sidetone returns at ~10-20%
                                    # of original amplitude (~RMS 200-400). Real human speech is louder.
    MIN_SPEECH_PACKETS = 5          # Require ≥5 consecutive packets (100ms) above threshold before
                                    # treating as real speech — rejects single-packet echo spikes.
    MAX_SPEECH_PACKETS = 600        # Max 12s per utterance turn to prevent infinite buffering
    turn_index = 0
    idle_silence_packet_count = 0
    inactivity_timeouts_count = 0
    ai_is_speaking = False
    
    tts_queue = asyncio.Queue()
    stop_playback_flag = asyncio.Event()
    playback_task = None

    # Enable debug mode to save streamed WAV files for side-by-side comparison with Plivo recordings
    SAVE_STREAM_DEBUG_WAV = os.getenv("DEBUG_VOICE_AUDIO", "true").lower() == "true"
    DEBUG_AUDIO_DIR = Path(__file__).resolve().parents[3] / "temp" / "debug_audio"
    if SAVE_STREAM_DEBUG_WAV:
        DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    awaiting_feedback = False

    websocket_closed = False  # Guard: never send after close

    async def stream_sentence_audio(sentence: str):
        nonlocal websocket_closed
        try:
            from app.voice.tts import TextToSpeech
            tts = TextToSpeech()
            lang = session.language if session else "en"

            # Stream mu-law chunks directly from edge_tts → ffmpeg pipe.
            # No sleep between chunks — Plivo's jitter buffer handles pacing.
            # Sleeping artificially gaps the audio stream and causes audible pauses.
            async for mulaw_chunk in tts.generate_mulaw_stream(sentence, language=lang):
                if stop_playback_flag.is_set() or websocket_closed:
                    break
                payload = base64.b64encode(mulaw_chunk).decode("utf-8")
                try:
                    await websocket.send_json({
                        "event": "playAudio",
                        "media": {
                            "contentType": "audio/x-mulaw",
                            "sampleRate": "8000",
                            "payload": payload
                        }
                    })
                except (RuntimeError, WebSocketDisconnect):
                    websocket_closed = True
                    stop_playback_flag.set()
                    return
        except (RuntimeError, WebSocketDisconnect):
            websocket_closed = True
            stop_playback_flag.set()
            return
        except Exception as e:
            if not websocket_closed:
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

    async def play_system_prompt(prompt_text: str):
        nonlocal ai_is_speaking, idle_silence_packet_count, playback_task
        ai_is_speaking = True
        try:
            stop_playback_flag.set()
            if stream_id:
                await websocket.send_json({"event": "clearAudio", "streamId": stream_id})
            if playback_task and not playback_task.done():
                playback_task.cancel()
            while not tts_queue.empty():
                try:
                    tts_queue.get_nowait()
                    tts_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            stop_playback_flag.clear()
            playback_task = asyncio.create_task(playback_worker())
            await tts_queue.put(prompt_text)
            await tts_queue.join()
        except Exception as e:
            print(f"Error playing system prompt: {e}")
        finally:
            ai_is_speaking = False
            idle_silence_packet_count = 0

    async def terminate_call_with_prompt(prompt_text: str):
        nonlocal ai_is_speaking, playback_task, websocket_closed
        ai_is_speaking = True
        try:
            stop_playback_flag.set()
            if stream_id and not websocket_closed:
                try:
                    await websocket.send_json({"event": "clearAudio", "streamId": stream_id})
                except Exception:
                    pass
            if playback_task and not playback_task.done():
                playback_task.cancel()
                try:
                    await playback_task
                except asyncio.CancelledError:
                    pass
            while not tts_queue.empty():
                try:
                    tts_queue.get_nowait()
                    tts_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            stop_playback_flag.clear()
            playback_task = asyncio.create_task(playback_worker())
            await tts_queue.put(prompt_text)
            await tts_queue.join()          # Wait for goodbye audio to fully stream
            await asyncio.sleep(1.2)        # Extra buffer so last audio chunk clears the network
            # Only close the socket after all audio is done
            if not websocket_closed:
                websocket_closed = True
                try:
                    await websocket.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"Error terminating call: {e}")

    async def process_voice_turn(audio_data: bytes):
        nonlocal ai_is_speaking, turn_index, awaiting_feedback, playback_task
        nonlocal idle_silence_packet_count, inactivity_timeouts_count
        try:
            lang_code = session.language if session else "en"
            from app.voice.ivr import PROMPTS
            lang_prompts = PROMPTS.get(lang_code, PROMPTS["en"])

            tracker = LatencyTracker("WebSocketVoiceTurn")
            tracker.log_stage("Incoming Request")
            
            wav_bytes = None
            try:
                upsample_proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y",
                    "-f", "mulaw",
                    "-ar", "8000",
                    "-ac", "1",
                    "-i", "-",
                    "-ar", "16000",
                    "-ac", "1",
                    "-c:a", "pcm_s16le",
                    "-f", "wav",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                wav_bytes, _ = await upsample_proc.communicate(input=audio_data)
            except Exception as ex:
                print(f"[WebSocket Stream] FFMPEG conversion error: {ex}")
                wav_bytes = None
                
            if not wav_bytes:
                ai_is_speaking = False
                return

            tracker.log_stage("Speech Recognition")
            from app.voice.stt import SpeechToText
            stt = SpeechToText()
            import inspect
            if inspect.iscoroutinefunction(stt.transcribe_bytes):
                transcription = await stt.transcribe_bytes(wav_bytes, language=session.language if session else "en")
            else:
                transcription = await asyncio.to_thread(stt.transcribe_bytes, wav_bytes, language=session.language if session else "en")
            print(f"[STT Raw] Transcription result: '{transcription}'")
            
            if not transcription or not transcription.strip():
                ai_is_speaking = False
                return
                
            clean_trans = transcription.strip()
            broadcast_call_event("new_transcript", session.session_id if session else call_uuid, f"Customer: {clean_trans}", {
                "sender": "USER",
                "message": clean_trans,
            })
            
            if awaiting_feedback:
                num_map = {
                    "0": 10, "10": 10, "zero": 10, "ten": 10, "shunya": 10, "शून्य": 10, "दस": 10,
                    "1": 1, "one": 1, "ek": 1, "एक": 1,
                    "2": 2, "two": 2, "do": 2, "दो": 2,
                    "3": 3, "three": 3, "teen": 3, "तीन": 3,
                    "4": 4, "four": 4, "chaar": 4, "चार": 4,
                    "5": 5, "five": 5, "paanch": 5, "पांच": 5, "पाँच": 5,
                    "6": 6, "six": 6, "chhah": 6, "छह": 6,
                    "7": 7, "seven": 7, "saat": 7, "सात": 7,
                    "8": 8, "eight": 8, "aath": 8, "आठ": 8,
                    "9": 9, "nine": 9, "nau": 9, "नौ": 9,
                }
                rating = None
                for word in clean_trans.split():
                    if word in num_map:
                        rating = num_map[word]
                        break
                if rating is None:
                    rating = 10
                print(f"[WebSocket Stream Feedback] Verbal rating received: {rating}/10 for Call UUID: {call_uuid}")
                if session:
                    session.state = IVRState.FEEDBACK_PENDING
                    session.advance_state("DTMF", str(rating))
                    db.commit()
                
                stop_playback_flag.set()
                if stream_id:
                    await websocket.send_json({"event": "clearAudio", "streamId": stream_id})
                if playback_task and not playback_task.done():
                    playback_task.cancel()
                while not tts_queue.empty():
                    try:
                        tts_queue.get_nowait()
                        tts_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                stop_playback_flag.clear()
                playback_task = asyncio.create_task(playback_worker())
                goodbye_msg = lang_prompts.get("goodbye", "Thank you for calling. Have a great day! Goodbye.")
                await tts_queue.put(goodbye_msg)
                await tts_queue.join()
                await asyncio.sleep(1.0)
                try:
                    await websocket.close()
                except:
                    pass
                return

            # Conversational turn
            from app.repositories.conversation_repository import ConversationRepository
            conv_repo = ConversationRepository(db)
            db_conv = conv_repo.get_or_create_session(
                session_id=session.session_id if session else f"ivr-{call_uuid}",
                user_id=session.user_id if session else None,
                channel="VOICE",
                language=session.language if session else "en"
            )
            
            tracker.log_stage("Conversation Memory")
            chat_req = ChatRequest(
                message=clean_trans,
                session_id=session.session_id if session else f"ivr-{call_uuid}"
            )
            
            sentence_accum = ""
            first_token = True

            # --- Start (or restart) the playback worker BEFORE queuing TTS sentences ---
            stop_playback_flag.set()
            if stream_id:
                try:
                    await websocket.send_json({"event": "clearAudio", "streamId": stream_id})
                except Exception:
                    pass
            if playback_task and not playback_task.done():
                playback_task.cancel()
            # Drain any stale queue items
            while not tts_queue.empty():
                try:
                    tts_queue.get_nowait()
                    tts_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            stop_playback_flag.clear()
            playback_task = asyncio.create_task(playback_worker())
            # -----------------------------------------------------------------

            async for token in chat_service.process_stream(
                request=chat_req,
                user_id=session.user_id if session else None,
                channel="TELEPHONY",
                audio_input_path=None,
                tracker=tracker
            ):
                if first_token:
                    tracker.log_stage("LLM")
                    first_token = False
                sentence_accum += token
                if any(sentence_accum.endswith(p) for p in (".", "?", "!", "\n", "।", "॥")):
                    sentence = sentence_accum.strip()
                    if sentence:
                        await tts_queue.put(sentence)
                    sentence_accum = ""
                    
            if sentence_accum.strip():
                await tts_queue.put(sentence_accum.strip())

            tracker.log_stage("Response Generation")

            from app.conversation.memory import memory
            mem_session = memory.get(session.session_id) if session else None
            full_resp = mem_session.last_response if mem_session else ""
            broadcast_call_event("new_transcript", session.session_id if session else call_uuid, f"AI: {full_resp}", {
                "sender": "AI",
                "message": full_resp,
            })
            
            if db_conv:
                db.refresh(db_conv)
                res_status = db_conv.resolution_status or "unresolved"
                lang = session.language if session else "en"
                broadcast_call_event("call_updated", session.session_id if session else call_uuid, f"Call state updated: {res_status}.", {
                    "resolution_status": res_status,
                    "language": lang,
                })

            if session:
                choose_prompt = lang_prompts.get(
                    "choose_query",
                    "If you want to ask another query, press 1. If your query is resolved, press 0."
                )
                await tts_queue.put(choose_prompt)

            tracker.log_stage("TTS")
            tracker.print_summary()

            await tts_queue.join()

            # Echo guard: wait for phone line sidetone/echo to decay before
            # releasing the half-duplex lock. Without this, the last 200-300ms
            # of TTS audio echoes back from the phone and triggers a ghost VAD turn.
            await asyncio.sleep(0.65)

        except Exception as err:
            print(f"Error in process_voice_turn: {err}")
        finally:
            # Flush the caller audio buffer and pre-roll so stale echo audio
            # from this turn is not prepended to the next turn's STT input.
            caller_audio_buffer.clear()
            pre_roll_buffer.clear()
            is_speaking = False
            silence_counter = 0
            speech_packet_count = 0
            ai_is_speaking = False
            idle_silence_packet_count = 0
            inactivity_timeouts_count = 0

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
                if ai_is_speaking:
                    # Strict half-duplex turn-taking: ignore inbound audio while AI is speaking
                    continue
                
                media = msg.get("media", {})
                payload_b64 = media.get("payload")
                if not payload_b64:
                    continue
                
                payload = base64.b64decode(payload_b64)
                rms = get_mulaw_rms(payload)
                
                if rms > RMS_SPEECH_THRESHOLD:
                    silence_counter = 0
                    idle_silence_packet_count = 0
                    inactivity_timeouts_count = 0
                    if not is_speaking:
                        speech_packet_count += 1
                        caller_audio_buffer.extend(payload)
                        # Require MIN_SPEECH_PACKETS consecutive loud packets before confirming speech.
                        # This rejects single-packet echo bursts from phone sidetone.
                        if speech_packet_count >= MIN_SPEECH_PACKETS:
                            is_speaking = True
                            print(f"[VAD] Caller speaking detected (RMS: {rms:.1f}). Prepending pre-roll lead-in buffer ({len(pre_roll_buffer)} packets / {len(pre_roll_buffer)*20}ms)...")
                            
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

                            # Prepend pre-roll lead-in audio to preserve initial soft consonants/words
                            pre_buf = bytes(caller_audio_buffer)  # save buffered pre-confirm audio
                            caller_audio_buffer.clear()
                            for packet in pre_roll_buffer:
                                caller_audio_buffer.extend(packet)
                            caller_audio_buffer.extend(pre_buf)   # append the confirmed speech so far
                            pre_roll_buffer.clear()
                    else:
                        caller_audio_buffer.extend(payload)
                        speech_packet_count += 1
                else:
                    # Keep continuous 500ms ring buffer of lead-in audio while caller is silent
                    pre_roll_buffer.append(payload)
                    
                    if is_speaking:
                        silence_counter += 1
                        speech_packet_count += 1
                        caller_audio_buffer.extend(payload)
                        
                        if silence_counter >= SILENCE_THRESHOLD_PACKETS or speech_packet_count >= MAX_SPEECH_PACKETS:
                            turn_index += 1
                            duration_sec = round((len(caller_audio_buffer) / 8000), 2)
                            print(f"[VAD] Complete utterance detected (packets={speech_packet_count}, duration={duration_sec}s, silence_packets={silence_counter}). Processing query...")
                            
                            is_speaking = False
                            silence_counter = 0
                            speech_packet_count = 0
                            
                            audio_data = bytes(caller_audio_buffer)
                            caller_audio_buffer.clear()
                            
                            if len(audio_data) >= 8000:  # At least 1.0s total audio
                                ai_is_speaking = True  # strict half-duplex turn ownership
                                asyncio.create_task(process_voice_turn(audio_data))
                    else:
                        # Echo burst decayed before reaching MIN_SPEECH_PACKETS — reset the counter
                        # so accumulated echo packets don't eventually cross the gate later.
                        if speech_packet_count > 0 and speech_packet_count < MIN_SPEECH_PACKETS:
                            speech_packet_count = 0
                            caller_audio_buffer.clear()
                        # Inactivity timeout tracking (starts only after AI finishes speaking)
                        playback_idle = (playback_task is None or playback_task.done()) and tts_queue.empty()
                        if playback_idle and not awaiting_feedback:
                            idle_silence_packet_count += 1
                            if idle_silence_packet_count >= 300:  # ~6 seconds of complete silence (300 * 20ms)
                                idle_silence_packet_count = 0
                                lang_code = session.language if session else "en"
                                from app.voice.ivr import PROMPTS
                                lang_prompts = PROMPTS.get(lang_code, PROMPTS["en"])
                                
                                if inactivity_timeouts_count < 1:
                                    inactivity_timeouts_count += 1
                                    print(f"[WebSocket Stream] Inactivity timeout 1 triggered for Call UUID: {call_uuid}")
                                    timeout_msg = lang_prompts.get(
                                        "timeout_reminder",
                                        "We didn't receive any input. Press 1 to continue with another query, or 0 to finish."
                                    )
                                    asyncio.create_task(play_system_prompt(timeout_msg))
                                else:
                                    print(f"[WebSocket Stream] Inactivity timeout 2 triggered. Terminating Call UUID: {call_uuid}")
                                    goodbye_msg = lang_prompts.get("goodbye", "Thank you for calling. Have a great day! Goodbye.")
                                    asyncio.create_task(terminate_call_with_prompt(goodbye_msg))
                                    break

            elif event == "dtmf":
                dtmf_obj = msg.get("dtmf") or msg.get("media") or {}
                digit = str(
                    dtmf_obj.get("digit")
                    or msg.get("digit")
                    or msg.get("data")
                    or ""
                ).strip()
                print(f"[WebSocket Stream DTMF] Received keypress '{digit}' for Call UUID: {call_uuid}")
                idle_silence_packet_count = 0
                inactivity_timeouts_count = 0
                
                lang_code = session.language if session else "en"
                from app.voice.ivr import PROMPTS
                lang_prompts = PROMPTS.get(lang_code, PROMPTS["en"])

                if awaiting_feedback:
                    # Capture rating keypress (1 to 9, or 0 for 10)
                    rating = 10 if digit == "0" else (int(digit) if digit.isdigit() else 10)
                    print(f"[WebSocket Stream Feedback] Caller rated experience: {rating}/10 for Call UUID: {call_uuid}")
                    if session:
                        from app.voice.ivr import IVRState
                        session.state = IVRState.FEEDBACK_PENDING
                        session.advance_state("DTMF", digit)
                        db.commit()

                    goodbye_msg = lang_prompts.get("goodbye", "Thank you for calling. Have a great day! Goodbye.")
                    # Await directly — do NOT use create_task+break here.
                    # create_task+break causes the finally block to cancel the playback_task
                    # before the goodbye audio finishes, producing the ASGI close-then-send error.
                    await terminate_call_with_prompt(goodbye_msg)
                    break

                elif digit == "0":
                    print(f"[WebSocket Stream DTMF] User selected 0 (Query Resolved). Prompting for 1-10 feedback rating...")
                    awaiting_feedback = True
                    feedback_msg = lang_prompts.get(
                        "feedback",
                        "Thank you. Please rate your support experience from 1 to 10 using your telephone keypad, where 0 represents a rating of 10."
                    )
                    asyncio.create_task(play_system_prompt(feedback_msg))

                elif digit == "1":
                    print(f"[WebSocket Stream DTMF] User selected 1 (Ask another query). Clearing audio, prompting for next question...")
                    awaiting_feedback = False
                    caller_audio_buffer.clear()
                    pre_roll_buffer.clear()
                    is_speaking = False
                    silence_counter = 0
                    speech_packet_count = 0
                    
                    speak_msg = lang_prompts.get("speak_query", "Please speak your query now.")
                    asyncio.create_task(play_system_prompt(speak_msg))

            elif event == "stop":
                print(f"[WebSocket Stream] Stop event for Call UUID: {call_uuid}")
                break
    except WebSocketDisconnect:
        print(f"[WebSocket Stream] Disconnected for Call UUID: {call_uuid}")
    except Exception as e:
        print(f"[WebSocket Stream] WebSocket Error: {e}")
    finally:
        stop_playback_flag.set()
        if playback_task and not playback_task.done():
            playback_task.cancel()
            try:
                await playback_task
            except asyncio.CancelledError:
                pass
        db.close()
