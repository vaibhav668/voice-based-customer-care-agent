from sqlalchemy.orm import Session

from app.ai.tools.booking import BookingTool
from app.ai.tools.cancellation import CancellationTool
from app.ai.tools.create_booking import CreateBookingTool
from app.ai.tools.delay import DelayTool
from app.ai.tools.faq import FAQTool
from app.ai.tools.refund import RefundTool


class ToolRegistry:

    def __init__(self, db: Session):

        self.tools = {
            "BOOKING_STATUS": BookingTool(db),
            "BUS_DELAY": DelayTool(db),
            "BOOKING_CANCEL": CancellationTool(db),
            "REFUND_STATUS": RefundTool(db),
            "CREATE_BOOKING": CreateBookingTool(db),
            "FAQ": FAQTool(),
        }

    def get(self, intent: str):
        return self.tools.get(intent)