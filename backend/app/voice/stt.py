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

    # Language-aware Whisper prompts — short, non-enumerable sentences so Whisper cannot
    # hallucinate them verbatim as a transcription when it receives low-quality audio.
    LANGUAGE_PROMPTS = {
        "en": "A customer is calling a bus company support line about their travel booking.",
        "hi": "एक यात्री बस सेवा के ग्राहक समर्थन से अपनी यात्रा के बारे में बात कर रहा है।",
        "te": "ఒక ప్రయాణికుడు బస్ సేవ కస్టమర్ కేర్‌తో తన ప్రయాణం గురించి మాట్లాడుతున్నాడు.",
        "ta": "ஒரு பயணி பஸ் சேவை வாடிக்கையாளர் ஆதரவிடம் தனது பயணம் பற்றி பேசுகிறார்.",
        "kn": "ಒಬ್ಬ ಪ್ರಯಾಣಿಕ ಬಸ್ ಸೇವೆಯ ಗ್ರಾಹಕ ಸೇವೆಯೊಂದಿಗೆ ತಮ್ಮ ಪ್ರಯಾಣದ ಬಗ್ಗೆ ಮಾತನಾಡುತ್ತಿದ್ದಾರೆ.",
        "mr": "एक प्रवासी बस सेवेच्या ग्राहक सहाय्य केंद्राशी आपल्या प्रवासाबद्दल बोलत आहे.",
        "gu": "એક મુસાફર બસ સેવાના ગ્રાહક સહાય સાથે તેની મુસાફરી વિશે વાત કરી રહ્યો છે.",
        "bn": "একজন যাত্রী বাস সেবার গ্রাহক সহায়তার সাথে তার ভ্রমণ নিয়ে কথা বলছেন।",
        "ml": "ഒരു യാത്രക്കാരൻ ബസ് സേവനത്തിന്റെ ഗ്രാഹക സേവനവുമായി തന്റെ യാത്രയെ കുറിച്ച് സംസാരിക്കുന്നു.",
    }

    # Prompt keyword fragments — used to detect Whisper hallucinating the prompt verbatim
    HALLUCINATION_FRAGMENTS = {
        "en": ["calling a bus company", "customer is calling"],
        "hi": ["बस सेवा के ग्राहक", "यात्री बस सेवा", "ग्राहक समर्थन"],
        "te": ["బస్ సేవ కస్టమర్", "ప్రయాణికుడు బస్"],
        "ta": ["பஸ் சேவை வாடிக்கை", "பயணி பஸ்"],
        "kn": ["ಬಸ್ ಸೇವೆಯ ಗ್ರಾಹಕ", "ಪ್ರಯಾಣಿಕ ಬಸ್"],
        "mr": ["बस सेवेच्या ग्राहक", "प्रवासी बस"],
        "gu": ["બસ સેવાના ગ્રાહક", "મુસાફર બસ"],
        "bn": ["বাস সেবার গ্রাহক", "যাত্রী বাস"],
        "ml": ["ബസ് സേവനത്തിന്റെ", "യാത്രക്കാരൻ ബസ്"],
    }

    # Known hallucination keyword patterns — used to detect Whisper hallucinating domain lists
    HALLUCINATION_KEYWORDS = [
        "बुकिंग कोड", "टिकट स्थिति", "रिफंड", "लाइव ट्रैकिंग", "रद्द करना",
        "सीट नंबर", "प्रस्थान समय", "गंतव्य", "booking code", "ticket status",
        "live tracking", "departure time", "destination"
    ]

    def transcribe(
        self,
        audio_path: str,
        language: str = "en",
    ) -> str:

        lang_code = (language or "en").lower().strip()
        if lang_code not in {"en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "ur"}:
            lang_code = "en"

        # Note: We intentionally do NOT supply a prompt parameter here because
        # Whisper-large-v3 on Groq uses prompt to bias context and frequently hallucinates
        # words from the prompt parameter when processing low-bitrate phone audio.
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    response_format="text",
                    language=lang_code,
                    temperature=0.0,
                )
        except Exception as e:
            print(f"[STT] Notice: whisper-large-v3-turbo failed ({e}), falling back to whisper-large-v3")
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text",
                    language=lang_code,
                    temperature=0.0,
                )

        result = transcription.strip()

        if not result:
            return ""

        # Hallucination Guard 1: Detect comma-separated keyword enumerations or repetitive outputs
        result_lower = result.lower()
        keyword_hits = sum(1 for kw in self.HALLUCINATION_KEYWORDS if kw.lower() in result_lower)
        if keyword_hits >= 2:
            print(f"[STT] Keyword list hallucination detected ({keyword_hits} hits), discarding: {result[:80]}")
            return ""

        # Hallucination Guard 2: Detect prompt fragment matches
        fragments = self.HALLUCINATION_FRAGMENTS.get(lang_code, [])
        if any(frag.lower() in result_lower for frag in fragments):
            print(f"[STT] Prompt fragment hallucination detected, discarding: {result[:80]}")
            return ""

        # Hallucination Guard 3: Detect exact comma-separated repetitive list patterns
        if "," in result or "،" in result or "।" in result:
            parts = [p.strip() for p in result.replace("،", ",").replace("।", ",").split(",") if p.strip()]
            if len(parts) >= 2 and len(set(parts)) < len(parts):
                # Contains duplicate phrases separated by commas/punctuation
                print(f"[STT] Repetitive phrase loop detected, discarding: {result[:80]}")
                return ""

        return result