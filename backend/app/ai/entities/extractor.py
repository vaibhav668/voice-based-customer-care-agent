import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.entities.schemas import ExtractedEntities
from app.ai.llm.factory import get_llm
from app.ai.utils.json_parser import parse_json

llm = get_llm()

ENTITY_PROMPT = """
You are an information extraction engine.

Extract ONLY:

1. passenger_name
2. complaint

Do NOT extract booking codes.
Do NOT extract bus numbers.

Return ONLY valid JSON.

{
    "passenger_name": null,
    "complaint": null
}
"""


# -----------------------------------------------------
# Booking Code Normalization
# -----------------------------------------------------

def normalize_booking_code(text: str) -> str:

    text = text.upper()

    text = text.replace(" DASH ", "-")
    text = text.replace("DASH ", "-")
    text = text.replace("DASH", "-")

    text = text.replace("BOOKING CODE", "")
    text = text.replace("BOOKING ID", "")
    text = text.replace("BOOKING NUMBER", "")

    # BK100001 -> BK-100001
    text = re.sub(
        r"BK\s*-?\s*(\d{6})",
        r"BK-\1",
        text,
    )

    return text


# -----------------------------------------------------
# Booking Code Extraction
# -----------------------------------------------------

def extract_booking_code(text: str):

    text = normalize_booking_code(text)

    match = re.search(
        r"BK-\d{6}",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group().upper()

    return None


# -----------------------------------------------------
# Bus Number Extraction
# -----------------------------------------------------

def extract_bus_number(text: str):

    match = re.search(
        r"BUS\s*(?:NUMBER)?\s*([A-Z0-9-]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    return None


# -----------------------------------------------------
# Main Extraction
# -----------------------------------------------------

def extract_entities(message: str) -> ExtractedEntities:

    booking_code = extract_booking_code(message)

    bus_number = extract_bus_number(message)

    messages = [
        SystemMessage(content=ENTITY_PROMPT),
        HumanMessage(content=message),
    ]

    response = llm.invoke(messages)

    if hasattr(response, "content"):
        response = response.content

    print("=" * 60)
    print("ENTITY RESPONSE")
    print(response)
    print("=" * 60)

    try:

        data = parse_json(response)

    except Exception:

        print("Failed to parse entity JSON.")

        data = {
            "passenger_name": None,
            "complaint": None,
        }

    data["booking_code"] = booking_code
    data["bus_number"] = bus_number

    return ExtractedEntities(**data)