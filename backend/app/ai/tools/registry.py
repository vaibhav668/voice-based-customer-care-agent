from sqlalchemy.orm import Session

from app.ai.tools.booking import BookingTool
from app.ai.tools.cancellation import CancellationTool
from app.ai.tools.create_booking import CreateBookingTool
from app.ai.tools.delay import DelayTool
from app.ai.tools.faq import FAQTool
from app.ai.tools.refund import RefundTool
from app.ai.tools.complaint import ComplaintTool
from app.ai.tools.tracking import TrackingTool
from app.ai.tools.payment import PaymentTool
from app.ai.tools.reschedule import RescheduleTool
from app.ai.tools.list_bookings import ListBookingsTool


class ToolRegistry:

    def __init__(self, db: Session):

        self.tools = {
            "BOOKING_STATUS": BookingTool(db),
            "BUS_DELAY": DelayTool(db),
            "BOOKING_CANCEL": CancellationTool(db),
            "REFUND_STATUS": RefundTool(db),
            "CREATE_BOOKING": CreateBookingTool(db),
            "FAQ": FAQTool(),
            "COMPLAINT": ComplaintTool(db),
            "BUS_TRACKING": TrackingTool(db),
            "PAYMENT_ISSUE": PaymentTool(db),
            "RESCHEDULE": RescheduleTool(db),
            "LIST_BOOKINGS": ListBookingsTool(db),
        }

    def get(self, intent: str):
        return self.tools.get(intent)