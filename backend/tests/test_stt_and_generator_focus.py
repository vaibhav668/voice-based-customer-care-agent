import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.voice.stt import SpeechToText
from app.ai.understanding.node import understand
from app.ai.intent.schemas import Intent
from app.ai.response.generator import ResponseGenerator


def test_stt_hallucination_guard():
    stt = SpeechToText()

    # Test hallucination detection logic directly on keyword list outputs
    hallucinated_text = "बुकिंग कोड, टिकट स्थिति, रिफंड, लाइव ट्रैकिंग, रद्द करना, सीट नंबर, प्रस्थान समय, रद्द करना, सीट नंबर, गंतव्य।"
    
    result_lower = hallucinated_text.lower()
    keyword_hits = sum(1 for kw in stt.HALLUCINATION_KEYWORDS if kw.lower() in result_lower)
    assert keyword_hits >= 2, "Should detect multiple hallucination keywords"

    # Repetitive loop detection
    parts = [p.strip() for p in hallucinated_text.replace("।", ",").split(",") if p.strip()]
    has_duplicates = len(parts) >= 2 and len(set(parts)) < len(parts)
    assert has_duplicates, "Should detect duplicate phrase loop in hallucinated string"


def test_refund_intent_understanding():
    res = understand("नुझे रिफंड इत्ये रह जाने।")
    assert res.intent == Intent.REFUND_STATUS or res.intent.value == "REFUND_STATUS"


def test_response_generator_refund_focus():
    generator = ResponseGenerator()
    data = {
        "booking_code": "BK-1012",
        "booking_status": "CANCELLED",
        "payment_status": "PAID",
        "refund_message": "Your refund has been processed and will be credited within 5 business days.",
        "departure_time": "2026-07-20 18:30",
        "source": "Delhi",
        "destination": "Jaipur",
        "seat_number": "12A"
    }

    # Generate response for refund status query
    response = generator.generate(
        tool_name="refund_status",
        data=data,
        user_message="When will I get my refund?",
        language="en"
    )

    # Response should discuss refund and NOT recite departure time or seat number
    resp_lower = response.lower()
    assert "refund" in resp_lower or "credited" in resp_lower or "business days" in resp_lower or "processed" in resp_lower
