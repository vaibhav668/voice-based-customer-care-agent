from app.ai.intent.classifier import classify_intent

tests = [
    "Where is my booking?",
    "My bus is delayed.",
    "Cancel my ticket.",
    "I need a refund.",
    "I want to file a complaint.",
    "What is your refund policy?",
    "Hello",
]

for text in tests:
    print(text)
    print(classify_intent(text))
    print("-" * 40)