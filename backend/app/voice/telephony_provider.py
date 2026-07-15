import os
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from plivo import plivoxml


class TelephonyProvider(ABC):
    """Abstract interface defining required telephony template responses."""

    @abstractmethod
    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "") -> str:
        pass

    @abstractmethod
    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        pass

    @abstractmethod
    def generate_query_choice_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        pass

    @abstractmethod
    def generate_completion_response(self, prompt: str) -> str:
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

    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "") -> str:
        """Generates Plivo XML requesting DTMF keypad inputs, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="dtmf",
            num_digits=num_digits or 99,
            execution_timeout=8
        )
        get_input.add(plivoxml.SpeakElement(prompt))
        response.add(get_input)
        return response.to_string()

    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        """Generates Plivo XML playing TTS audio and waiting for spoken caller response, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="speech",
            speech_model="default",
            execution_timeout=7,
            speech_end_timeout=2
        )
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            get_input.add(plivoxml.SpeakElement(text_prompt))
        response.add(get_input)
        return response.to_string()

    def generate_query_choice_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        """Generates Plivo XML playing TTS audio and waiting for DTMF choice, resolving absolute action URL."""
        abs_action_url = self._get_absolute_url(action_url)
        response = plivoxml.ResponseElement()
        get_input = plivoxml.GetInputElement(
            action=abs_action_url,
            method="POST",
            input_type="dtmf",
            num_digits=1,
            execution_timeout=8
        )
        if audio_url:
            get_input.add(plivoxml.PlayElement(audio_url))
        else:
            get_input.add(plivoxml.SpeakElement(text_prompt))
        response.add(get_input)
        return response.to_string()

    def generate_completion_response(self, prompt: str) -> str:
        """Generates Plivo XML saying goodbye and hanging up."""
        response = plivoxml.ResponseElement()
        response.add(plivoxml.SpeakElement(prompt))
        response.add(plivoxml.HangupElement())
        return response.to_string()
