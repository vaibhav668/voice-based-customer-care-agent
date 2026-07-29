import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.understanding.node import understand

test_cases = [
    ("నా సీట్ కన్ఫర్మ్ అయిందా?", "booking status / seat confirmation"),
    ("నేను సీట్ మార్చుకోవచ్చా?", "seat change policy / FAQ"),
    ("నా సీట్ నంబర్ ఎంత?", "seat number"),
    ("నా బుకింగ్ కన్ఫర్మ్ అయిందా?", "booking status"),
]

for text, expected in test_cases:
    print(f"\nUser: {text} (Expected: {expected})", flush=True)
    res = understand(text)
    print(f"Parsed: Intent={res.intent}, Seat Number={res.seat_number}, Keywords={res.search_keywords}", flush=True)
