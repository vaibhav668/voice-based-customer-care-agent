from enum import Enum

from pydantic import BaseModel


class Intent(str, Enum):
    BOOKING_STATUS = "BOOKING_STATUS"
    BUS_DELAY = "BUS_DELAY"
    CANCEL_BOOKING = "CANCEL_BOOKING"
    REFUND = "REFUND"
    COMPLAINT = "COMPLAINT"
    FAQ = "FAQ"
    GENERAL = "GENERAL"


class IntentResult(BaseModel):
    intent: Intent