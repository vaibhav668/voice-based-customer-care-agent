import os
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from plivo import plivoxml


class TelephonyProvider(ABC):
    """Abstract interface defining required telephony template responses."""

    @abstractmethod
    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "", audio_url: str = "", language: str = "en") -> str:
        pass

    @abstractmethod
    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        pass

    @abstractmethod
    def generate_query_choice_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        pass

    @abstractmethod
    def generate_completion_response(self, prompt: str, language: str = "en", audio_url: str = "") -> str:
        pass

    @abstractmethod
    def generate_stream_response(self, stream_url: str, keep_call_alive: bool = True) -> str:
        pass


class PlivoAdapter(TelephonyProvider):
    """Concrete adapter mapping unified IVR instructions to XML Plivo responses with absolute URLs."""

    def __init__(self):
        self.auth_token = os.getenv("PLIVO_AUTH_TOKEN", "")
        self.public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
        if self.public_url.endswith("/"):
            self.public_url = self.public_url[:-1]

    def _get_absolute_url(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if not url.startswith("/"):
            url = f"/{url}"
        return f"{self.public_url}{url}"

    def _map_language(self, language: str) -> str:
        """Maps internal language codes to Plivo TTS language codes matching Polly voice capabilities.
        
        Prevents XML validation crashes on Plivo by ensuring language tag matches selected voice.
        """
        lang_lower = (language or "en").lower()
        mapping = {
            "en": "en-US",
            "hi": "hi-IN",
            "mr": "hi-IN",
            "ur": "hi-IN",
            "te": "hi-IN",
            "ta": "hi-IN",
            "kn": "hi-IN",
            "gu": "en-IN",
            "bn": "en-IN",
            "ml": "hi-IN",
        }
        return mapping.get(lang_lower, "en-US")

    def _map_asr_language(self, language: str) -> str:
        """Maps internal language codes to standard BCP 47 language tags for ASR recognition."""
        lang_lower = (language or "en").lower()
        mapping = {
            "en": "en-US",
            "hi": "hi-IN",
            "mr": "hi-IN",
            "te": "hi-IN",
            "ta": "hi-IN",
            "kn": "hi-IN",
            "gu": "en-IN",
            "bn": "en-IN",
            "ml": "hi-IN",
            "ur": "hi-IN",
        }
        return mapping.get(lang_lower, "en-IN")

    def _map_voice(self, language: str) -> str:
        """Maps language code to supported Plivo TTS voices."""
        lang_lower = (language or "en").lower()
        hindi_voice = os.getenv("PLIVO_HINDI_VOICE", "WOMAN")
        mapping = {
            "en": "Polly.Raveena",   # Indian English Female (Plivo supported)
            "hi": "Polly.Raveena",       # Hindi Female (Standard polite WOMAN voice or PLIVO_HINDI_VOICE)
            "te": "Polly.Aditi",     # Telugu - Aditi bilingual Indian voice
            "ta": "Polly.Aditi",     # Tamil - Aditi bilingual Indian voice
            "mr": hindi_voice,       # Marathi - Devanagari polite voice
            "kn": "Polly.Aditi",     # Kannada - Aditi bilingual Indian voice
            "gu": "Polly.Raveena",   # Gujarati - Raveena Indian voice
            "bn": "Polly.Raveena",   # Bengali - Raveena Indian voice
            "ml": "Polly.Aditi",     # Malayalam - Aditi bilingual Indian voice
            "ur": hindi_voice,       # Urdu - Hindustani polite voice
        }
        return mapping.get(lang_lower, hindi_voice)

    def validate_signature(self, method: str, url: str, nonce: str, signature: str, params: Dict[str, Any]) -> bool:
        """Validates that incoming webhook calls originated from Plivo servers."""
        # Allow disabling signature validation in local/mock environments
        if os.getenv("PLIVO_VALIDATE_SIGNATURE", "false").lower() != "true":
            return True
        if not signature or not nonce:
            return False
        try:
            from plivo.utils import validate_v3_signature
            return validate_v3_signature(method, url, nonce, self.auth_token, signature, params)
        except Exception:
            return False

    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "", audio_url: str = "", language: str = "en") -> str:
        """Generates Plivo XML requesting DTMF keypad inputs, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="dtmf",
            num_digits=num_digits or 99,
            execution_timeout=20,
            finish_on_key="#"
        )
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            plivo_lang = self._map_language(language)
            get_input.add(plivoxml.SpeakElement(prompt, voice=self._map_voice(language), language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        """Generates Plivo XML playing TTS audio and waiting for spoken caller response, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        
        if (language or "en").lower() != "en":
            # For non-English regional languages, play/speak the prompt and record user voice directly
            if audio_url:
                response.add(plivoxml.PlayElement(audio_url))
            else:
                plivo_lang = self._map_language(language)
                response.add(plivoxml.SpeakElement(text_prompt, voice=self._map_voice(language), language=plivo_lang))
            
            record = plivoxml.RecordElement(
                action=abs_action_url,
                method="POST",
                max_length=30,
                play_beep=True,
                file_format="mp3",
                redirect=True,
                timeout=5,
            )
            response.add(record)
            return response.to_string()
            
        asr_lang = self._map_asr_language(language)
        # input_type=speech only
        # speech_end_timeout=2 is the minimum allowed by Plivo (less than 2 causes XML validation failure)
        # execution_timeout=30 gives caller up to 30s total to speak their query
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="speech",
            execution_timeout=30,
            speech_end_timeout=2,
            language=asr_lang,
        )
        
        plivo_lang = self._map_language(language)
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            get_input.add(plivoxml.SpeakElement(text_prompt, voice=self._map_voice(language), language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_query_choice_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        """Generates Plivo XML playing TTS audio and waiting for DTMF or speech choice, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        
        if (language or "en").lower() != "en":
            # Use DTMF only for non-English languages to bypass ASR inaccuracies or crashes
            get_input = plivoxml.GetInputElement(
                action=abs_action_url,
                method="POST",
                input_type="dtmf",
                num_digits=1,
                execution_timeout=15,
            )
        else:
            asr_lang = self._map_asr_language(language)
            # IMPORTANT: When input_type is mixed (DTMF and speech), we must use space separation "dtmf speech"
            # and we must not set num_digits. Also, speech_end_timeout must be >= 2.
            get_input = plivoxml.GetInputElement(
                action=abs_action_url,
                method="POST",
                input_type="dtmf speech",
                execution_timeout=15,
                speech_end_timeout=2,
                language=asr_lang,
            )
            
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            plivo_lang = self._map_language(language)
            get_input.add(plivoxml.SpeakElement(text_prompt, voice=self._map_voice(language), language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_completion_response(self, prompt: str, language: str = "en", audio_url: str = "") -> str:
        """Generates Plivo XML saying goodbye and hanging up."""
        response = plivoxml.ResponseElement()
        if audio_url:
            response.add(plivoxml.PlayElement(audio_url))
        else:
            plivo_lang = self._map_language(language)
            response.add(plivoxml.SpeakElement(prompt, voice=self._map_voice(language), language=plivo_lang))
        response.add(plivoxml.HangupElement())
        return response.to_string()

    def generate_stream_response(self, stream_url: str, keep_call_alive: bool = True) -> str:
        """Generates Plivo XML starting a bidirectional WebSocket audio stream."""
        response = plivoxml.ResponseElement()
        stream = plivoxml.StreamElement(
            stream_url,
            bidirectional=True,
            keepCallAlive=keep_call_alive,
            contentType="audio/x-mulaw;rate=8000"
        )
        response.add(stream)
        return response.to_string()
