import enum
import uuid
import json
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models.user import User
from app.database.models.ivr_session import IvrSession
from app.repositories.conversation_repository import ConversationRepository
from app.voice.service import VoiceService
from app.websocket.routes import manager


class IVRState(str, enum.Enum):
    INCOMING = "INCOMING"
    RECORDING_CONSENT_PENDING = "RECORDING_CONSENT_PENDING"
    LANGUAGE_SELECTION_PENDING = "LANGUAGE_SELECTION_PENDING"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFICATION_PHONE_PENDING = "VERIFICATION_PHONE_PENDING"
    ACTIVE_AGENT = "ACTIVE_AGENT"
    FEEDBACK_PENDING = "FEEDBACK_PENDING"
    COMPLETED = "COMPLETED"


def broadcast_call_event(event_type: str, session_id: str, message: str, data: Optional[dict] = None):
    """Sends real-time WebSocket CRM notifications to all listening admin dashboards."""
    payload = {
        "event": event_type,
        "session_id": session_id,
        "message": message,
        "data": data or {},
    }
    manager.broadcast_sync(json.dumps(payload))


class IVRCallSession:

    def __init__(
        self,
        call_id: str,
        phone_number: str,
        db: Session,
    ):
        self.call_id = call_id
        self.phone_number = "".join(filter(str.isdigit, phone_number))[-10:] if phone_number else ""
        self.db = db
        
        self.state = IVRState.INCOMING
        self.recording_consent: Optional[bool] = None
        self.language: str = "en"
        self.user_id: Optional[str] = None
        self.session_id: str = f"ivr-{call_id}"
        self.booking_code: Optional[str] = None
        
        # Resolve caller identity securely
        self._identify_caller()

    def load_from_row(self, row: IvrSession):
        """Initializes state from database record."""
        self.call_id = row.call_id
        self.phone_number = row.phone_number
        self.state = IVRState(row.state)
        self.recording_consent = row.recording_consent
        self.language = row.language
        self.user_id = row.user_id
        self.session_id = row.session_id
        self.booking_code = row.booking_code

    def _save_to_db(self):
        """Persists the session details back to PostgreSQL/SQLite."""
        row = self.db.query(IvrSession).filter_by(call_id=self.call_id).first()
        if not row:
            row = IvrSession(call_id=self.call_id)
            self.db.add(row)
        
        row.phone_number = self.phone_number
        row.state = self.state.value
        row.recording_consent = self.recording_consent
        row.language = self.language
        row.user_id = self.user_id
        row.session_id = self.session_id
        row.booking_code = self.booking_code
        self.db.commit()

    def _log_system_event(self, message: str):
        """Logs a turn-by-turn system lifecycle event as a ConversationMessage."""
        conv_repo = ConversationRepository(self.db)
        conv = conv_repo.get_or_create_session(
            session_id=self.session_id,
            user_id=self.user_id,
            channel="VOICE",
            language=self.language,
        )
        
        # Insert SYSTEM sender conversation message log
        from app.repositories.conversation_message_repository import ConversationMessageRepository
        msg_repo = ConversationMessageRepository(self.db)
        msg_repo.add_message(
            conversation_id=conv.id,
            sender="SYSTEM",
            message_type="VOICE",
            message=message,
            booking_code=self.booking_code,
        )

    def _identify_caller(self):
        """Matches caller's phone number against registered users."""
        if not self.phone_number:
            return
        
        stmt = select(User).where(User.phone.like(f"%{self.phone_number}"))
        user = self.db.scalar(stmt)
        if user:
            self.user_id = str(user.id)
            self.language = user.preferred_language or "en"

    def advance_state(self, action: str, data: Optional[str] = None) -> dict:
        """
        Processes IVR inputs (DTMF or voice) and transitions the call state.
        Returns the instructions (audio prompts and expected input types) for the IVR engine.
        """
        # Ensure database Conversation record exists immediately
        conv_repo = ConversationRepository(self.db)
        conv = conv_repo.get_or_create_session(
            session_id=self.session_id,
            user_id=self.user_id,
            channel="VOICE",
            language=self.language,
        )

        if self.state == IVRState.INCOMING:
            self.state = IVRState.RECORDING_CONSENT_PENDING
            self._save_to_db()
            self._log_system_event("Call incoming. Prompting user for recording consent.")
            broadcast_call_event("call_started", self.session_id, "Voice call started.", {"phone_number": self.phone_number})
            
            return {
                "state": self.state.value,
                "prompt": "This call may be recorded for quality purposes. Press 1 to consent, or 2 to opt-out.",
                "expect_input": "DTMF",
            }

        elif self.state == IVRState.RECORDING_CONSENT_PENDING:
            if action == "DTMF":
                if data == "1":
                    self.recording_consent = True
                    self._log_system_event("Recording consent accepted.")
                elif data == "2":
                    self.recording_consent = False
                    self._log_system_event("Recording consent rejected.")
                
                self.state = IVRState.LANGUAGE_SELECTION_PENDING
                self._save_to_db()
                broadcast_call_event("call_updated", self.session_id, "Call recording consent updated.", {"recording_consent": self.recording_consent})
                
                return {
                    "state": self.state.value,
                    "prompt": "Select your preferred language. Press 1 for English, 2 for Hindi, or 3 for Telugu.",
                    "expect_input": "DTMF",
                }

        elif self.state == IVRState.LANGUAGE_SELECTION_PENDING:
            if action == "DTMF":
                if data == "1":
                    self.language = "en"
                elif data == "2":
                    self.language = "hi"
                elif data == "3":
                    self.language = "te"
                
                self._log_system_event(f"Language set to {self.language.upper()}.")
                conv.language = self.language
                self.db.commit()

                # Run caller ID matching
                self._identify_caller()
                broadcast_call_event("call_updated", self.session_id, f"Language set to {self.language}.", {"language": self.language})

                # Check if caller matches user ID
                if self.user_id:
                    self.state = IVRState.ACTIVE_AGENT
                    self._save_to_db()
                    self._log_system_event("Caller identified and verified automatically via caller ID.")
                    
                    welcome_msg = "Welcome back! How can I assist you with your booking today?"
                    if self.language == "hi":
                        welcome_msg = "स्वागत है! आज मैं आपकी बुकिंग में कैसे सहायता कर सकता हूँ?"
                    elif self.language == "te":
                        welcome_msg = "స్వాగతం! ఈరోజు మీ బుకింగ్‌లో నేను మీకు ఎలా సహాయపడగలను?"

                    broadcast_call_event("call_updated", self.session_id, "Caller verified. Active Agent started.", {"state": "ACTIVE_AGENT", "user_id": self.user_id})

                    return {
                        "state": self.state.value,
                        "prompt": welcome_msg,
                        "expect_input": "VOICE",
                    }
                else:
                    self.state = IVRState.VERIFICATION_PENDING
                    self._save_to_db()
                    self._log_system_event("Caller verification pending. Asking for booking reference code.")
                    return {
                        "state": self.state.value,
                        "prompt": "We could not verify your phone number. Please key in your 6 digit booking reference code.",
                        "expect_input": "DTMF",
                    }

        elif self.state == IVRState.VERIFICATION_PENDING:
            booking_code = data.strip().upper() if (action == "DTMF" and data) else ""
            if booking_code:
                if not booking_code.startswith("BK-") and len(booking_code) == 6:
                    booking_code = f"BK-{booking_code}"
                
                # Retrieve booking record from DB
                from app.repositories.booking_repository import BookingRepository
                booking_repo = BookingRepository(self.db)
                booking = booking_repo.get_booking_with_trip(booking_code)
                
                if not booking:
                    self._log_system_event(f"Caller verification failed: booking {booking_code} not found.")
                    return {
                        "state": self.state.value,
                        "prompt": "Invalid booking reference. Please enter your 6 digit booking reference code again.",
                        "expect_input": "DTMF",
                    }

                self.booking_code = booking_code
                
                # Check if booking is linked to a user profile
                if booking.user_id and booking.user:
                    # Enforce secure two-step caller validation
                    self.state = IVRState.VERIFICATION_PHONE_PENDING
                    self._save_to_db()
                    self._log_system_event(f"Booking {booking_code} found. Prompting for registered phone number.")
                    
                    return {
                        "state": self.state.value,
                        "prompt": "Please enter the 10-digit registered phone number associated with this booking.",
                        "expect_input": "DTMF",
                    }
                else:
                    # Guest booking
                    self.state = IVRState.ACTIVE_AGENT
                    self._save_to_db()
                    
                    conv.booking_id = booking.id
                    self.db.commit()

                    self._log_system_event(f"Verified guest booking {booking_code}. Entering active support agent.")
                    
                    from app.conversation.manager import ConversationManager
                    manager_inst = ConversationManager()
                    session = manager_inst.get_session(self.session_id)
                    session.entities["booking_code"] = booking_code
                    
                    broadcast_call_event("call_updated", self.session_id, f"Guest booking {booking_code} verified.", {"state": "ACTIVE_AGENT", "booking_code": booking_code})

                    return {
                        "state": self.state.value,
                        "prompt": "Thank you, reference verified. Please speak your support request now.",
                        "expect_input": "VOICE",
                    }
            else:
                return {
                    "state": self.state.value,
                    "prompt": "Booking code not received. Please key in your 6 digit booking reference code using your keypad.",
                    "expect_input": "DTMF",
                }

        elif self.state == IVRState.VERIFICATION_PHONE_PENDING:
            input_phone = "".join(filter(str.isdigit, data))[-10:] if (action == "DTMF" and data) else ""
            if input_phone:
                # Lookup the booking
                from app.repositories.booking_repository import BookingRepository
                booking_repo = BookingRepository(self.db)
                booking = booking_repo.get_booking_with_trip(self.booking_code)
                
                if booking and booking.user:
                    owner_phone = "".join(filter(str.isdigit, booking.user.phone))[-10:]
                    if input_phone == owner_phone:
                        # Successfully verified registered customer phone number!
                        self.user_id = str(booking.user_id)
                        self.state = IVRState.ACTIVE_AGENT
                        self._save_to_db()

                        # Link verified entities to database conversation
                        conv.user_id = booking.user_id
                        conv.booking_id = booking.id
                        self.db.commit()

                        self._log_system_event("Caller phone verification successful. Entering active support agent.")

                        from app.conversation.manager import ConversationManager
                        manager_inst = ConversationManager()
                        session = manager_inst.get_session(self.session_id)
                        session.entities["booking_code"] = self.booking_code
                        
                        broadcast_call_event("call_updated", self.session_id, f"Verification successful for user {self.user_id}.", {
                            "state": "ACTIVE_AGENT",
                            "booking_code": self.booking_code,
                            "user_id": self.user_id,
                        })

                        return {
                            "state": self.state.value,
                            "prompt": "Thank you, verification successful. Please speak your support request now.",
                            "expect_input": "VOICE",
                        }

                # Mismatch / failure
                self._log_system_event("Caller phone verification failed: registered phone mismatch.")
                return {
                    "state": self.state.value,
                    "prompt": "Verification failed. Please enter the 10-digit registered phone number again.",
                    "expect_input": "DTMF",
                }
            else:
                return {
                    "state": self.state.value,
                    "prompt": "Phone number not received. Please key in your 10-digit registered phone number associated with this booking.",
                    "expect_input": "DTMF",
                }

        elif self.state == IVRState.ACTIVE_AGENT:
            return {
                "state": self.state.value,
                "prompt": "Active support session. Send voice input.",
                "expect_input": "VOICE",
            }

        elif self.state == IVRState.FEEDBACK_PENDING:
            rating = None
            if action == "DTMF" and data:
                digit = data.strip()
                if digit == "0":
                    rating = 10
                elif digit.isdigit() and 1 <= int(digit) <= 9:
                    rating = int(digit)

            if rating is not None:
                from app.database.models.customer_feedback import CustomerFeedback
                fb = CustomerFeedback(
                    conversation_id=conv.id,
                    user_id=conv.user_id,
                    rating=rating,
                )
                self.db.add(fb)
                self.db.commit()
                self._log_system_event(f"Customer feedback rating received: {rating}.")
                broadcast_call_event("feedback_submitted", self.session_id, f"Customer submitted rating: {rating}", {
                    "rating": rating,
                    "phone_number": self.phone_number,
                })
            else:
                self._log_system_event("Customer feedback skipped or invalid.")

            self.state = IVRState.COMPLETED
            self._save_to_db()
            self.complete_call()
            return {
                "state": self.state.value,
                "prompt": "Thank you for your feedback. Goodbye.",
                "expect_input": "NONE",
            }

        return {
            "state": self.state.value,
            "prompt": "Thank you for calling. The call is completed.",
            "expect_input": "NONE",
        }

    async def process_voice_agent_turn(self, audio_path: str, audio_relative_path: Optional[str] = None) -> dict:
        """Processes voice turn: STT -> ChatAgent -> TTS."""
        if self.state != IVRState.ACTIVE_AGENT:
            return {"error": "Voice inputs are only allowed during the active agent state."}

        voice_service = VoiceService(db=self.db)
        
        # Process speech agent loop
        res = await voice_service.process(
            audio_path=audio_path,
            audio_relative_path=audio_relative_path,
            session_id=self.session_id,
            language=self.language,
            user_id=self.user_id,
            db=self.db,
        )

        # Retrieve resolution status updates
        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        res_status = conv.resolution_status if conv else "unresolved"

        if conv and conv.resolution_status == "resolved" and self.state == IVRState.ACTIVE_AGENT:
            self.state = IVRState.FEEDBACK_PENDING
            self._save_to_db()
            self._log_system_event("Conversation completed. Prompting for customer feedback rating.")
            
            feedback_prompt = "Thank you. Please rate your support experience from 1 to 10 using your telephone keypad, where 0 represents a rating of 10."
            if self.language == "hi":
                feedback_prompt = "धन्यवाद। कृपया अपने सहायता अनुभव को 1 से 10 के पैमाने पर रेट करें, जहाँ 0 का अर्थ 10 है।"
            elif self.language == "te":
                feedback_prompt = "ధన్యవాదాలు. దయచేసి మీ టెలిఫోన్ కీప్యాడ్ ఉపయోగించి మీ సహాయ అనుభవాన్ని 1 నుండి 10 వరకు రేట్ చేయండి, ఇక్కడ 0 అంటే 10."
                
            res["text"] = res.get("text", "") + " " + feedback_prompt
            res["expect_input"] = "DTMF"
            res["state"] = self.state.value
            
            broadcast_call_event("call_updated", self.session_id, "Prompting for customer feedback rating.", {
                "state": self.state.value,
                "resolution_status": conv.resolution_status
            })

        # Broadcast turn-by-turn transcripts and tool changes
        broadcast_call_event("new_transcript", self.session_id, f"Customer: {res.get('transcript')}", {
            "sender": "USER",
            "transcript": res.get("transcript"),
        })
        broadcast_call_event("new_transcript", self.session_id, f"AI: {res.get('text')}", {
            "sender": "AI",
            "transcript": res.get("text"),
        })
        
        # Broadcast status syncs
        if conv:
            broadcast_call_event("call_updated", self.session_id, f"Call state updated: {res_status}.", {
                "current_intent": conv.current_intent,
                "last_tool": conv.last_tool,
                "resolution_status": res_status,
            })

        return res

    async def process_text_agent_turn(self, text: str) -> dict:
        """Processes voice turn when transcription is already available (e.g. from Twilio SpeechResult)."""
        if self.state != IVRState.ACTIVE_AGENT:
            return {"error": "Voice inputs are only allowed during the active agent state."}

        from app.schemas.chat import ChatRequest
        from app.services.chat_service import ChatService
        chat_service = ChatService(db=self.db)
        
        res_chat = chat_service.process(
            request=ChatRequest(
                session_id=self.session_id,
                message=text,
                language=self.language,
            ),
            user_id=self.user_id,
            channel="VOICE",
        )

        from app.voice.tts import TextToSpeech
        tts = TextToSpeech()
        generated_audio = await tts.generate(
            res_chat["response"],
            language=self.language,
        )

        if res_chat.get("db_message_id"):
            try:
                from app.database.models.conversation_message import ConversationMessage
                db_msg = self.db.get(ConversationMessage, res_chat["db_message_id"])
                if db_msg:
                    db_msg.audio_path = generated_audio
                    self.db.commit()
            except Exception as e:
                print("Voice DB audio path sync notice:", e)

        res = {
            "session_id": res_chat["session_id"],
            "transcript": text,
            "text": res_chat["response"],
            "audio_path": generated_audio,
        }

        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        res_status = conv.resolution_status if conv else "unresolved"

        if conv and conv.resolution_status == "resolved" and self.state == IVRState.ACTIVE_AGENT:
            self.state = IVRState.FEEDBACK_PENDING
            self._save_to_db()
            self._log_system_event("Conversation completed. Prompting for customer feedback rating.")
            
            feedback_prompt = "Thank you. Please rate your support experience from 1 to 10 using your telephone keypad, where 0 represents a rating of 10."
            if self.language == "hi":
                feedback_prompt = "धन्यवाद। कृपया अपने सहायता अनुभव को 1 से 10 के पैमाने पर रेट करें, जहाँ 0 का अर्थ 10 है।"
            elif self.language == "te":
                feedback_prompt = "ధన్యవాదాలు. దయచేసి మీ టెలిఫోన్ కీప్యాడ్ ఉపయోగించి మీ సహాయ అనుభవాన్ని 1 నుండి 10 వరకు రేట్ చేయండి, ఇక్కడ 0 అంటే 10."
                
            res["text"] = res.get("text", "") + " " + feedback_prompt
            res["expect_input"] = "DTMF"
            res["state"] = self.state.value
            
            broadcast_call_event("call_updated", self.session_id, "Prompting for customer feedback rating.", {
                "state": self.state.value,
                "resolution_status": conv.resolution_status
            })

        broadcast_call_event("new_transcript", self.session_id, f"Customer: {text}", {
            "sender": "USER",
            "transcript": text,
        })
        broadcast_call_event("new_transcript", self.session_id, f"AI: {res.get('text')}", {
            "sender": "AI",
            "transcript": res.get('text'),
        })
        
        if conv:
            broadcast_call_event("call_updated", self.session_id, f"Call state updated: {res_status}.", {
                "current_intent": conv.current_intent,
                "last_tool": conv.last_tool,
                "resolution_status": res_status,
            })

        return res

    def complete_call(self) -> dict:
        """Gracefully completes the active call, setting ended_at and closing the DB conversation."""
        self.state = IVRState.COMPLETED
        self._save_to_db()

        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        if conv:
            from app.database.models.conversation import ConversationStatus
            conv.status = ConversationStatus.CLOSED
            conv.ended_at = datetime.utcnow()
            self._log_system_event(f"Call disconnected/completed. Resolution: {conv.resolution_status}.")
            self.db.commit()

            broadcast_call_event("call_ended", self.session_id, "Call disconnected.", {
                "resolution_status": conv.resolution_status,
                "ended_at": conv.ended_at.isoformat()
            })

        return {
            "status": "completed",
            "message": "Call successfully ended.",
            "session_id": self.session_id,
        }


class IVRManager:
    """Database-backed IVR Call Session Store."""

    def __init__(self):
        self.calls: Dict[str, IVRCallSession] = {}

    def get_or_create_call(self, call_id: str, phone_number: str, db: Session) -> IVRCallSession:
        # Check local cache first
        if call_id in self.calls:
            self.calls[call_id].db = db
            return self.calls[call_id]

        # Check database persistence strategy
        row = db.query(IvrSession).filter_by(call_id=call_id).first()
        if row:
            session = IVRCallSession(call_id, phone_number, db)
            session.load_from_row(row)
            self.calls[call_id] = session
            return session

        # Otherwise create new session record
        session = IVRCallSession(call_id, phone_number, db)
        session._save_to_db()
        self.calls[call_id] = session
        return session


ivr_manager = IVRManager()
