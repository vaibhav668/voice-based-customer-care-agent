import asyncio
import uuid
from pathlib import Path

import edge_tts

VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
    "te": "te-IN-MohanNeural",
    "ta": "ta-IN-PallaviNeural",
    "kn": "kn-IN-GaganNeural",
    "gu": "gu-IN-DhwaniNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "ur": "ur-IN-GulNeural",
}


class TextToSpeech:

    def __init__(self):

        self.output_dir = Path(__file__).parent.parent.parent / "generated_audio"
        self.output_dir.mkdir(exist_ok=True)

    async def generate(
        self,
        text: str,
        language: str = "en",
    ) -> str:

        filename = f"{uuid.uuid4()}.mp3"

        output_path = self.output_dir / filename

        voice = VOICE_MAP.get((language or "en").lower(), "en-US-AriaNeural")

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
        )

        await communicate.save(str(output_path))

        return f"generated_audio/{filename}"