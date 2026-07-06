from enum import Enum

from pydantic import BaseModel


class Intent(str, Enum):

    BOOKING_STATUS = "BOOKING_STATUS"

    BUS_DELAY = "BUS_DELAY"

    BOOKING_CANCEL = "BOOKING_CANCEL"

    REFUND_STATUS = "REFUND_STATUS"

    COMPLAINT = "COMPLAINT"

    FAQ = "FAQ"

    PROVIDE_BOOKING_CODE = "PROVIDE_BOOKING_CODE"

    FOLLOW_UP = "FOLLOW_UP"

    CREATE_BOOKING = "CREATE_BOOKING"

    GENERAL = "GENERAL"


class IntentResult(BaseModel):

    intent: Intent