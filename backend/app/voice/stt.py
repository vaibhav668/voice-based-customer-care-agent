from pathlib import Path
import os
import io

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
        "en": "A customer is calling a bus company support line about their travel booking. They may ask about booking status, seat number, delays, refunds, cancellation, luggage, or pets allowed policy.",
        "hi": "एक यात्री बस सेवा के ग्राहक समर्थन से अपनी यात्रा बुकिंग, बुकिंग कोड, रिफंड, रद्दीकरण (cancellation), सीट नंबर, देरी (delay), सामान (luggage) या पेट्स (pets allowed) की नीति के बारे में बात कर रहा है।",
        "te": "ఒక ప్రయాణికుడు బస్ కస్టమర్ కేర్‌తో తన బుకింగ్ స్టేటస్, రీఫండ్, టికెట్ క్యాన్సిలేషన్, బస్సు ఆలస్యం, సీటు నంబర్ లేదా లగేజ్ పాలసీ గురించి మాట్లాడుతున్నాడు.",
        "ta": "ஒரு பயணி பஸ் வாடிக்கையாளர் சேவையிடம் தனது முன்பதிவு நிலை, ரீஃபண்ட், ரத்து செய்தல், பஸ் தாமதம், இருக்கை எண் அல்லது லக்கேஜ் கொள்கை பற்றி பேசுகிறார்.",
        "kn": "ಒಬ್ಬ ಪ್ರಯಾಣಿಕ ಬಸ್ ಗ್ರಾಹಕ ಸೇವೆಯೊಂದಿಗೆ ತಮ್ಮ ಬುಕಿಂಗ್ ಸ್ಥಿತಿ, ಮರುಪಾವತಿ (refund), ರದ್ದತಿ (cancellation), ಬಸ್ ವಿಳಂಬ (delay), ಸೀಟ್ ಸಂಖ್ಯೆ ಅಥವಾ ಲಗೇಜ್ ನೀತಿಯ ಬಗ್ಗೆ ಮಾತನಾಡುತ್ತಿದ್ದಾರೆ.",
        "mr": "एक प्रवासी बस सेवेच्या ग्राहक केंद्राशी आपल्या बुकिंग स्थिती, रिफंड, तिकीट रद्द करणे, बस उशीर (delay), सीट नंबर किंवा सामान (luggage) पॉलिसीबद्दल बोलत आहे.",
        "gu": "એક મુસાફર બસ સેવાના ગ્રાહક પ્રતિનિધિ સાથે બુકિંગ સ્ટેટસ, રિફંડ, કેન્સલેશન, બસ મોડી (delay) હોવા અંગે, સીટ નંબર અથવા સામાન (luggage) પોલિસી વિશે વાત કરી રહ્યો છે.",
        "bn": "একজন যাত্রী বাস গ্রাহক পরিষেবার সাথে তার বুকিং স্ট্যাটাস, রিফান্ড, বুকিং বাতিলকরণ, বাস বিলম্ব, সিট নম্বর বা লাগেজ পলিসি নিয়ে কথা বলছেন।",
        "ml": "ഒരു യാത്രക്കാരൻ ബസ് കസ്റ്റമർ സർവീസുമായി തന്റെ ബുക്കിംഗ് നില, റീഫണ്ട്, റദ്ദാക്കൽ, ബസ് വൈകൽ, സീറ്റ് നമ്പർ അല്ലെങ്കിൽ ലഗേജ് പോളിസി എന്നിവയെക്കുറിച്ച് സംസാരിക്കുന്നു.",
        "pa": "ਇੱਕ ਯਾਤਰੀ ਬੱਸ ਸੇਵਾ ਦੇ ਗਾਹਕ ਸਹਾਇਤਾ ਨਾਲ ਆਪਣੀ ਬੁਕਿੰਗ ਸਥਿਤੀ, ਰਿਫੰਡ, ਰੱਦ ਕਰਨ (cancellation), ਬੱਸ ਦੇਰੀ (delay), ਸੀਟ ਨੰਬਰ ਜਾਂ ਸਮਾਨ (luggage) ਦੀ ਨੀਤੀ ਬਾਰੇ ਗੱਲ ਕਰ ਰਿਹਾ ਹੈ।",
        "ur": "ایک مسافر بس کسٹمر سروس سے بکنگ، ریفنڈ، منسوخی (cancellation)، تاخیر (delay)، سیٹ نمبر یا سامان کی پالیسی کے بارے میں بات کر رہا ہے۔",
    }

    # Prompt keyword fragments — used to detect Whisper hallucinating the prompt verbatim
    HALLUCINATION_FRAGMENTS = {
        "en": ["calling a bus company", "customer is calling"],
        "hi": ["बस सेवा के ग्राहक", "यात्री बस सेवा", "ग्राहक समर्थन"],
        "te": ["బస్ సేవ కస్టమర్", "ప్రయాణికుడు బస్"],
        "ta": ["பஸ் சேவை வாடிக்கை", "பயணி பஸ்"],
        "kn": ["ಬಸ್ ಸೇವೆಯ ಗ್ರಾಹಕ", "ಪ್ರಯಾಣಿಕ బస్"],
        "mr": ["बस सेवेच्या ग्राहक", "प्रवासी बस"],
        "gu": ["બસ સેવાના ગ્રાહਕ", "મુસાફર બસ"],
        "bn": ["বাস সেবার গ্রাহক", "যাত্রী বাস"],
        "ml": ["ബസ് സേവനത്തിന്റെ", "യാത്രക്കാരൻ ബസ്"],
        "pa": ["ਬੱਸ ਸੇਵਾ ਦੇ", "ਯਾਤਰੀ ਬੱਸ"],
        "ur": ["بس سروس کے", "مسافر بس"],
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
        if lang_code not in {"en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "pa", "ur"}:
            lang_code = "en"

        prompt_text = self.LANGUAGE_PROMPTS.get(lang_code, self.LANGUAGE_PROMPTS["en"])

        try:
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text",
                    language=lang_code,
                    prompt=prompt_text,
                    temperature=0.0,
                )
        except Exception as e:
            print(f"[STT] Notice: whisper-large-v3 failed ({e}), falling back without prompt parameter...")
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text",
                    language=lang_code,
                    temperature=0.0,
                )

        result = transcription.strip()
        return self._filter_hallucinations(result, lang_code)

    def transcribe_bytes(
        self,
        wav_bytes: bytes,
        language: str = "en",
    ) -> str:
        lang_code = (language or "en").lower().strip()
        if lang_code not in {"en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "pa", "ur"}:
            lang_code = "en"

        prompt_text = self.LANGUAGE_PROMPTS.get(lang_code, self.LANGUAGE_PROMPTS["en"])

        try:
            transcription = self.client.audio.transcriptions.create(
                file=("audio.wav", wav_bytes, "audio/wav"),
                model="whisper-large-v3",
                response_format="text",
                language=lang_code,
                prompt=prompt_text,
                temperature=0.0,
            )
        except Exception as e:
            print(f"[STT] Notice: transcribe_bytes whisper-large-v3 failed ({e}), falling back without prompt parameter...")
            transcription = self.client.audio.transcriptions.create(
                file=("audio.wav", wav_bytes, "audio/wav"),
                model="whisper-large-v3",
                response_format="text",
                language=lang_code,
                temperature=0.0,
            )

        result = transcription.strip()
        return self._filter_hallucinations(result, lang_code)

    def _filter_hallucinations(self, result: str, lang_code: str) -> str:
        if not result:
            return ""

        result_lower = result.lower()
        keyword_hits = sum(1 for kw in self.HALLUCINATION_KEYWORDS if kw.lower() in result_lower)
        if keyword_hits >= 3 and ("," in result or "•" in result):
            print(f"[STT] Keyword list hallucination detected ({keyword_hits} hits), discarding: {result[:80]}")
            return ""

        # Hallucination Guard 2: Detect prompt fragment matches
        fragments = self.HALLUCINATION_FRAGMENTS.get(lang_code, [])
        if any(frag.lower() in result_lower for frag in fragments):
            print(f"[STT] Prompt fragment hallucination detected, discarding: {result[:80]}")
            return ""

        # Hallucination Guard 3: Detect exact comma-separated repetitive list patterns
        if "," in result or "•" in result or "।" in result:
            parts = [p.strip() for p in result.replace("।", ",").split(",") if p.strip()]
            if len(parts) >= 2 and len(set(parts)) < len(parts):
                # Contains duplicate phrases separated by commas/punctuation
                print(f"[STT] Repetitive phrase loop detected, discarding: {result[:80]}")
                return ""

        return result