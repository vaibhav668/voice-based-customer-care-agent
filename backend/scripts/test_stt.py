from app.voice.stt import SpeechToText

stt = SpeechToText()

text = stt.transcribe(r"C:\Users\vpokh\Desktop\support-ai\backend\scripts\sample-speech-1m.wav")

print("\nTranscription:")
print(text)