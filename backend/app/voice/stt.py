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

    # Language-aware Whisper prompts — native-script keywords strongly bias the model
    # toward producing output in the correct language and script.
    LANGUAGE_PROMPTS = {
        "en": (
            "Customer support phone call for bus travel service. "
            "Keywords: booking code, ticket status, refund, bus delay, live tracking, "
            "reschedule, cancellation, seat number, departure time, arrival time."
        ),
        "hi": (
            "बस यात्रा सेवा के लिए ग्राहक सहायता फोन कॉल। "
            "कीवर्ड: बुकिंग कोड, टिकट स्थिति, रिफंड, बस देरी, लाइव ट्रैकिंग, "
            "रद्द करना, सीट नंबर, प्रस्थान समय, आगमन समय, गंतव्य।"
        ),
        "te": (
            "బస్ ప్రయాణ సేవ కోసం కస్టమర్ సపోర్ట్ ఫోన్ కాల్. "
            "కీవర్డ్స్: బుకింగ్ కోడ్, టికెట్ స్థితి, రిఫండ్, బస్ ఆలస్యం, "
            "రద్దు, సీటు నంబర్, నిర్గమన సమయం, రాక సమయం, గమ్యం."
        ),
        "ta": (
            "பஸ் பயண சேவைக்கான வாடிக்கையாளர் ஆதரவு தொலைபேசி அழைப்பு. "
            "முக்கியச் சொற்கள்: பதிவு குறியீடு, டிக்கெட் நிலை, திரும்பப் பெறுதல், "
            "பேருந்து தாமதம், ரத்து, இருக்கை எண், புறப்படும் நேரம், வருகை நேரம்."
        ),
        "kn": (
            "ಬಸ್ ಪ್ರಯಾಣ ಸೇವೆಗಾಗಿ ಗ್ರಾಹಕ ಬೆಂಬಲ ಫೋನ್ ಕರೆ. "
            "ಕೀವರ್ಡ್‌ಗಳು: ಬುಕಿಂಗ್ ಕೋಡ್, ಟಿಕೆಟ್ ಸ್ಥಿತಿ, ಮರುಪಾವತಿ, ಬಸ್ ವಿಳಂಬ, "
            "ರದ್ದತಿ, ಆಸನ ಸಂಖ್ಯೆ, ನಿರ್ಗಮನ ಸಮಯ, ಆಗಮನ ಸಮಯ."
        ),
        "mr": (
            "बस प्रवास सेवेसाठी ग्राहक समर्थन फोन कॉल. "
            "कीवर्ड: बुकिंग कोड, तिकीट स्थिती, परतावा, बस विलंब, "
            "रद्द करणे, आसन क्रमांक, निघण्याची वेळ, आगमन वेळ, गंतव्य."
        ),
        "gu": (
            "બસ મુસાફરી સેવા માટે ગ્રાહક સહાય ફોન કૉલ. "
            "કીવર્ડ: બુકિંગ કોડ, ટિકિટ સ્થિતિ, રિફંડ, બસ વિલંબ, "
            "રદ કરવું, બેઠક નંબર, પ્રસ્થાન સમય, આગમન સમય, ગંતવ્ય."
        ),
        "bn": (
            "বাস ভ্রমণ সেবার জন্য গ্রাহক সহায়তা ফোন কল. "
            "কীওয়ার্ড: বুকিং কোড, টিকিট অবস্থা, ফেরত, বাস বিলম্ব, "
            "বাতিল, আসন নম্বর, ছাড়ার সময়, আগমনের সময়, গন্তব্য."
        ),
        "ml": (
            "ബസ് യാത്രാ സേവനത്തിനുള്ള കസ്റ്റമർ സപ്പോർട്ട് ഫോൺ കോൾ. "
            "കീവേഡുകൾ: ബുക്കിംഗ് കോഡ്, ടിക്കറ്റ് സ്റ്റാറ്റസ്, റീഫണ്ട്, ബസ് കാലതാമസം, "
            "റദ്ദാക്കൽ, സീറ്റ് നമ്പർ, പുറപ്പെടൽ സമയം, വരവ് സമയം, ലക്ഷ്യസ്ഥാനം."
        ),
    }

    def transcribe(
        self,
        audio_path: str,
        language: str = "en",
    ) -> str:

        lang_code = (language or "en").lower().strip()
        if lang_code not in {"en", "hi", "mr", "te", "ta", "kn", "gu", "bn", "ml", "ur"}:
            lang_code = "en"

        # Use native-script prompt for the detected language to prevent Whisper from
        # hallucinating English output when the caller speaks a regional language.
        prompt_text = self.LANGUAGE_PROMPTS.get(lang_code, self.LANGUAGE_PROMPTS["en"])

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