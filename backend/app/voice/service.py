from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech


class VoiceService:

    def __init__(self, db: Session | None = None):

        self.chat_service = ChatService(db=db)

        self.stt = SpeechToText()

        self.tts = TextToSpeech()

    async def process(
        self,
        audio_path: str,
        session_id: str | None = None,
        language: str = "en",
        user_id: str | None = None,
        audio_relative_path: str | None = None,
        db: Session | None = None,
        append_text: str = "",
        generate_tts: bool = True,
    ):
        if db:
            self.chat_service = ChatService(db=db)

        # ---------------- Speech → Text ---------------- #

        transcript = self.stt.transcribe(audio_path, language=language)

        print("=" * 60)
        print("TRANSCRIBED TEXT:")
        print(transcript)
        print("=" * 60)

        # Use relative path for DB storage so frontend can build correct URL
        # Fall back to audio_path if no relative path provided (legacy support)
        db_audio_path = audio_relative_path or audio_path

        # ---------------- AI Chat ---------------- #

        response = self.chat_service.process(
            request=ChatRequest(
                session_id=session_id,
                message=transcript,
                language=language,
            ),
            user_id=user_id,
            channel="VOICE",
            audio_input_path=db_audio_path,
        )

        tts_text = response["response"]
        if append_text:
            tts_text = f"{tts_text} {append_text}"

        # ---------------- Text → Speech ---------------- #
        generated_audio = ""
        if generate_tts:
            try:
                generated_audio = await self.tts.generate(
                    tts_text,
                    language=language,
                )
            except Exception as e:
                print("Notice: Failed to generate TTS via edge-tts in VoiceService:", e)
                generated_audio = ""


        # Update DB AI Message with generated audio path
        if response.get("db_message_id"):
            try:
                from app.database.models.conversation_message import ConversationMessage
                db_msg = self.chat_service.db.get(ConversationMessage, response["db_message_id"])
                if db_msg:
                    db_msg.audio_path = generated_audio
                    self.chat_service.db.commit()
            except Exception as e:
                print("Voice DB audio path sync notice:", e)

        # ---------------- Response ---------------- #

        return {
            "session_id": response["session_id"],
            "transcript": transcript,
            "text": response["response"],
            "audio_path": generated_audio,
        }