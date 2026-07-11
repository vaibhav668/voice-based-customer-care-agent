import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.understanding.node import understand

res = understand("My phone number is 9568987360")
print("Intent:", res.intent)
print("Phone Number:", res.phone_number)
print("Raw JSON:", res.model_dump())
