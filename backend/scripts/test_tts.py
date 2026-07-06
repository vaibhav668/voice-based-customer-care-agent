from app.voice.tts import TextToSpeech

tts = TextToSpeech()

audio = tts.generate(
    "Hello Vaibhav. Your bus is delayed by twenty minutes."
)

print(audio)