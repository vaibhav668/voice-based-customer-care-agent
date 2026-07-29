import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.response.generator import ResponseGenerator

generator = ResponseGenerator()

booking_data = {
    "booking_code": "BK-1234",
    "seat_number": "12A",
    "booking_status": "CONFIRMED",
    "payment_status": "PAID",
    "bus_name": "Premium AC Sleeper",
    "bus_number": "AP-01-XX-9999",
    "source": "Hyderabad",
    "destination": "Bangalore",
    "departure_time": "2026-07-30 21:00",
    "arrival_time": "2026-07-31 06:00",
}

faq_data = {
    "answer": "Seat changes are available subject to seat availability on the same bus. Please contact customer support with your booking code to request a seat change."
}

test_scenarios = [
    {
        "tool": "booking_status",
        "data": booking_data,
        "msg": "నా సీట్ కన్ఫర్మ్ అయిందా?",
        "desc": "Is my seat confirmed? (Expect booking/seat confirmation only)"
    },
    {
        "tool": "faq",
        "data": faq_data,
        "msg": "నేను సీట్ మార్చుకోవచ్చా?",
        "desc": "Can I change my seat? (Expect seat change policy only)"
    },
    {
        "tool": "booking_status",
        "data": booking_data,
        "msg": "నా సీట్ నంబర్ ఎంత?",
        "desc": "What is my seat number? (Expect seat number only)"
    },
    {
        "tool": "booking_status",
        "data": booking_data,
        "msg": "నా బుకింగ్ కన్ఫర్మ్ అయిందా?",
        "desc": "Is my booking confirmed? (Expect booking status only)"
    }
]

for sc in test_scenarios:
    print(f"\n--- Scenario: {sc['desc']} ---")
    print(f"User Question: {sc['msg']}")
    resp = generator.generate(
        tool_name=sc["tool"],
        data=sc["data"],
        user_message=sc["msg"],
        language="te"
    )
    print(f"Assistant Response:\n{resp}\n")
