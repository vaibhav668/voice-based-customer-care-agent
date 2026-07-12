import os
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from twilio.request_validator import RequestValidator


class TelephonyProvider(ABC):
    """Abstract interface defining required telephony template responses."""

    @abstractmethod
    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "") -> str:
        pass

    @abstractmethod
    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        pass

    @abstractmethod
    def generate_completion_response(self, prompt: str) -> str:
        pass


class TwilioAdapter(TelephonyProvider):
    """Concrete adapter mapping unified IVR instructions to XML TwiML responses."""

    def __init__(self):
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.validator = RequestValidator(self.auth_token) if self.auth_token else None

    def validate_signature(self, url: str, params: Dict[str, Any], signature: str) -> bool:
        """Validates that incoming webhook calls originated from Twilio servers."""
        # Allow disabling signature validation in local/mock environments
        if os.getenv("TWILIO_VALIDATE_SIGNATURE", "false").lower() != "true":
            return True
        if not self.validator or not signature:
            return False
        return self.validator.validate(url, params, signature)

    def generate_menu_response(self, prompt: str, expect_input: str, num_digits: Optional[int] = None, action_url: str = "") -> str:
        """Generates TwiML requesting DTMF keypad inputs."""
        gather_attrs = f'action="{action_url}" method="POST"'
        if num_digits:
            gather_attrs += f' numDigits="{num_digits}"'
        
        twiml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
        twiml += f'    <Gather {gather_attrs} input="dtmf" timeout="8">\n'
        twiml += f'        <Say>{prompt}</Say>\n'
        twiml += f'    </Gather>\n'
        # Redirect back to incoming if they timed out
        twiml += f'    <Redirect method="POST">{action_url}</Redirect>\n'
        twiml += f'</Response>'
        return twiml

    def generate_voice_agent_response(self, audio_url: str, text_prompt: str, action_url: str) -> str:
        """Generates TwiML playing TTS audio and waiting for spoken caller response."""
        twiml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
        if audio_url:
            twiml += f'    <Play>{audio_url}</Play>\n'
        else:
            twiml += f'    <Say>{text_prompt}</Say>\n'
        
        # Gather caller spoken response
        twiml += f'    <Gather action="{action_url}" method="POST" input="speech" timeout="5" speechTimeout="auto" />\n'
        # Redirect back to agent hook if caller is silent
        twiml += f'    <Redirect method="POST">{action_url}</Redirect>\n'
        twiml += f'</Response>'
        return twiml

    def generate_completion_response(self, prompt: str) -> str:
        """Generates TwiML saying goodbye and hanging up."""
        twiml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
        twiml += f'    <Say>{prompt}</Say>\n'
        twiml += f'    <Hangup />\n'
        twiml += f'</Response>'
        return twiml
