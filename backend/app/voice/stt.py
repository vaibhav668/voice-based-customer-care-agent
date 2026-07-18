from pathlib import Path
import os

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class SpeechToText:

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for speech-to-text transcription.")

        print("Groq Key Loaded:", api_key[:10] + "...")

        self.client = Groq(
            api_key=api_key
        )

    def transcribe(
        self,
        audio_path: str,
        language: str = "en",
    ) -> str:

        lang_code = (language or "en").lower().strip()
        if lang_code not in {"en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "ur"}:
            lang_code = "en"

        prompt_text = (
            "Customer support phone call for bus travel service. "
            "Keywords: booking code, ticket status, refund status, bus delay, live tracking, "
            "reschedule, cancellation, seat number, departure time, arrival time, Hyderabad, Delhi, Goa."
        )

        with open(audio_path, "rb") as audio_file:
            # Explicitly specify target language code (e.g. 'te' for Telugu, 'hi' for Hindi)
            # and domain prompt to prevent language auto-detection errors or hallucinated translations.
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                response_format="text",
                language=lang_code,
                prompt=prompt_text,
                temperature=0,
            )

        return transcription.strip()