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
    "pa": "pa-IN-GurpreetNeural",
}

# Speed adjustment per language — regional languages benefit from slightly slower rate
# to preserve clarity on phone-quality 8kHz audio
VOICE_RATE = {
    "en": "+0%",
    "hi": "-5%",   # slightly slower for Devanagari prosody clarity
    "mr": "-5%",
    "te": "-5%",
    "ta": "-5%",
    "kn": "-5%",
    "gu": "-5%",
    "bn": "-5%",
    "ml": "-5%",
    "ur": "-5%",
    "pa": "-5%",
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
        """
        Generate TTS audio and save to MP3. Returns a relative path.
        Uses streaming internally to reduce time-to-first-byte for regional languages.
        """
        filename = f"{uuid.uuid4()}.mp3"
        output_path = self.output_dir / filename

        lang = (language or "en").lower()
        voice = VOICE_MAP.get(lang, "en-US-AriaNeural")
        rate = VOICE_RATE.get(lang, "+0%")

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
        )

        # Stream MP3 chunks directly into the file instead of buffering everything
        # first — reduces TTFB especially for Hindi/regional voices which have
        # larger phoneme models.
        with open(str(output_path), "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

        return f"generated_audio/{filename}"

    async def generate_mulaw_stream(
        self,
        text: str,
        language: str = "en",
    ):
        """
        Async generator that yields raw 8kHz mu-law PCM chunks directly from
        edge_tts without saving to disk. Eliminates the MP3-write + ffmpeg-read
        round-trip for the WebSocket streaming path.

        Yields bytes: raw G.711 mu-law chunks ready to send as Plivo playAudio payload.
        """
        lang = (language or "en").lower()
        voice = VOICE_MAP.get(lang, "en-US-AriaNeural")
        rate = VOICE_RATE.get(lang, "+0%")

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
        )

        # Pipe edge_tts MP3 stream → ffmpeg → mu-law without any disk I/O
        ffmpeg_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "mp3",          # input format
            "-i", "pipe:0",       # read from stdin
            "-ar", "8000",        # resample to 8kHz
            "-ac", "1",           # mono
            "-c:a", "pcm_mulaw",  # G.711 mu-law codec
            "-f", "mulaw",        # raw mu-law output
            "pipe:1",             # write to stdout
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # Feed MP3 chunks from edge_tts into ffmpeg stdin concurrently
        async def feed_ffmpeg():
            try:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        ffmpeg_proc.stdin.write(chunk["data"])
                ffmpeg_proc.stdin.close()
            except Exception:
                ffmpeg_proc.stdin.close()

        feed_task = asyncio.create_task(feed_ffmpeg())

        CHUNK = 320  # 40ms of 8kHz mono mu-law
        try:
            while True:
                data = await ffmpeg_proc.stdout.read(CHUNK)
                if not data:
                    break
                yield data
        finally:
            await feed_task
            try:
                await ffmpeg_proc.wait()
            except Exception:
                pass