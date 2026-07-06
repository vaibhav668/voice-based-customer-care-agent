from pydantic import BaseModel

from app.ai.intent.schemas import Intent


class UnderstandingResult(BaseModel):

    intent: Intent

    confidence: float = 1.0

    booking_code: str | None = None

    passenger_name: str | None = None

    complaint: str | None = None

    bus_number: str | None = None

    source_city: str | None = None

    destination_city: str | None = None

    travel_date: str | None = None

    seat_number: int | None = None

    # Captures explicit confirmation phrases like "YES", "YES CANCEL", "CONFIRM"
    # Used for the cancellation/reschedule confirmation gate
    confirmation: str | None = None