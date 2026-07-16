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
        """Maps internal language codes to Plivo TTS language codes.
        
        Only returns languages natively supported by Plivo standard/Polly TTS
        (en-US and hi-IN) to prevent XML validation crashes on unsupported locales.
        """
        mapping = {
            "en": "en-US",
            "hi": "hi-IN",
        }
        return mapping.get((language or "en").lower(), "en-US")

    def _map_asr_language(self, language: str) -> str:
        """Maps internal language codes to standard BCP 47 language tags for ASR recognition."""
        mapping = {
            "en": "en-US",
            "hi": "hi-IN",
            "te": "te-IN",
            "ta": "ta-IN",
            "mr": "mr-IN",
            "kn": "kn-IN",
            "gu": "gu-IN",
            "bn": "bn-IN",
            "ml": "ml-IN",
            "ur": "ur-IN",
        }
        return mapping.get((language or "en").lower(), "en-US")


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
            get_input.add(plivoxml.SpeakElement(prompt, language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        """Generates Plivo XML playing TTS audio and waiting for spoken caller response, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        
        asr_lang = self._map_asr_language(language)
        # input_type=speech only - num_digits is not valid with speech type
        # speech_end_timeout=1 means Plivo stops listening 1s after the caller stops talking
        # execution_timeout=30 gives caller up to 30s total to speak their query
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="speech",
            speech_model="default",
            execution_timeout=30,
            speech_end_timeout=1,
            language=asr_lang,
        )
        
        plivo_lang = self._map_language(language)
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            get_input.add(plivoxml.SpeakElement(text_prompt, language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_query_choice_response(self, audio_url: str, text_prompt: str, action_url: str, language: str = "en") -> str:
        """Generates Plivo XML playing TTS audio and waiting for DTMF or speech choice, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        asr_lang = self._map_asr_language(language)
        # IMPORTANT: When input_type is "dtmf,speech" (mixed), num_digits MUST NOT be set.
        # num_digits is only valid for pure "dtmf" input_type.
        # Setting num_digits with mixed input causes Plivo to throw "Invalid Action XML" and hang up.
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="dtmf,speech",
            execution_timeout=10,
            speech_end_timeout=1,
            language=asr_lang,
        )
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            plivo_lang = self._map_language(language)
            get_input.add(plivoxml.SpeakElement(text_prompt, language=plivo_lang))
        response.add(get_input)
        return response.to_string()

    def generate_completion_response(self, prompt: str, language: str = "en", audio_url: str = "") -> str:
        """Generates Plivo XML saying goodbye and hanging up."""
        response = plivoxml.ResponseElement()
        if audio_url:
            response.add(plivoxml.PlayElement(audio_url))
        else:
            plivo_lang = self._map_language(language)
            response.add(plivoxml.SpeakElement(prompt, language=plivo_lang))
        response.add(plivoxml.HangupElement())
        return response.to_string()
