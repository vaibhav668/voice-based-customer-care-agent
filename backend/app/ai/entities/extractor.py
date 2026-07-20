import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.entities.schemas import ExtractedEntities
from app.ai.llm.factory import get_llm
from app.ai.utils.json_parser import parse_json

llm = get_llm()

ENTITY_PROMPT = """
You are a highly accurate information extraction engine.

Your task is to extract only the requested entities from the user's message.

Extract ONLY the following fields:

1. passenger_name
2. complaint

Rules:

- Return ONLY valid JSON.
- Do not include explanations, markdown, comments, or additional text.
- Do not infer or guess missing information.
- If a field is not explicitly mentioned, return null.
- Preserve the original wording of the complaint as much as possible.
- Extract the passenger's actual name only if clearly provided.
- Do not confuse locations, cities, booking references, or bus numbers with passenger names.
- Ignore greetings, pleasantries, filler words, and conversational text.
- Ignore booking codes.
- Ignore booking IDs.
- Ignore reservation numbers.
- Ignore PNR numbers.
- Ignore ticket numbers.
- Ignore bus numbers.
- Ignore dates, times, phone numbers, and email addresses.
- Do not rewrite or summarize the complaint.
- Do not translate the complaint.
- Support multilingual input (English, Hindi, Marathi, Telugu, Tamil, Kannada, Malayalam, Bengali, Gujarati, Punjabi, and mixed-language sentences).
- Always preserve the user's original language in the extracted complaint.

Return this exact JSON schema:

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