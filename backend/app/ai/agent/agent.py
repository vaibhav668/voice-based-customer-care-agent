from sqlalchemy.orm import Session

from app.ai.schemas.tool_result import ToolResult
from app.ai.tools.registry import ToolRegistry
from app.ai.intent.schemas import Intent

class SupportAgent:

    def __init__(self, db: Session):
        self.db = db
        self.registry = ToolRegistry(db)

    def execute(
        self,
        intent: str,
        booking_code: str | None = None,
        question: str | None = None,
        source_city: str | None = None,
        destination_city: str | None = None,
        travel_date: str | None = None,
        seat_number: int | None = None,
        confirmation: str | None = None,
        user_id: str | None = None,
    ) -> ToolResult:

        # ----------------------------------------------------
        # Save Booking Code (Conversation Intent)
        # ----------------------------------------------------

        if intent == Intent.PROVIDE_BOOKING_CODE:

            if not booking_code:
                return ToolResult(
                    success=False,
                    tool=None,
                    data={
                        "message": "I couldn't find a booking code in your message."
                    },
                )

            return ToolResult(
                success=True,
                tool="save_booking",
                data={
                    "booking_code": booking_code,
                },
            )

        # ----------------------------------------------------
        # Booking Code Required
        # ----------------------------------------------------

        if intent in (
            Intent.BOOKING_STATUS,
            Intent.BUS_DELAY,
            Intent.BUS_TRACKING,
            Intent.BOOKING_CANCEL,
            Intent.REFUND_STATUS,
            Intent.PAYMENT_ISSUE,
            Intent.RESCHEDULE,
            ) and not booking_code:

            return ToolResult(
                success=False,
                tool=None,
                requires_booking_code=True,
                data={
                    "message": "Please provide your booking code."
                },
            )

        # ----------------------------------------------------
        # Get Tool
        # ----------------------------------------------------

        tool = self.registry.get(intent)

        if tool is None:

            return ToolResult(
                success=False,
                tool=None,
                data={
                    "message": f"Unsupported intent: {intent}"
                },
            )

        # ----------------------------------------------------
        # Create Booking
        # ----------------------------------------------------

        if intent == Intent.CREATE_BOOKING:
            try:
                data = tool.execute(
                    source=source_city or "Delhi",
                    destination=destination_city or "Hyderabad",
                    travel_date=travel_date,
                    seat_number=seat_number,
                    user_id=user_id,
                )
                return ToolResult(
                    success=True,
                    tool="create_booking",
                    data=data,
                )
            except Exception as e:
                self.db.rollback()
                return ToolResult(
                    success=False,
                    tool="create_booking",
                    data={"error": str(e), "message": "Failed to create booking."},
                )

        # ----------------------------------------------------
        # List Bookings
        # ----------------------------------------------------

        if intent == Intent.LIST_BOOKINGS:
            try:
                data = tool.execute(user_id=user_id)
                return ToolResult(
                    success=True,
                    tool="list_bookings",
                    data=data,
                )
            except Exception as e:
                self.db.rollback()
                return ToolResult(
                    success=False,
                    tool="list_bookings",
                    data={"error": str(e), "message": "Failed to list bookings."},
                )

        # ----------------------------------------------------
        # FAQ
        # ----------------------------------------------------

        if intent == Intent.FAQ:

            if not question:

                return ToolResult(
                    success=False,
                    tool="faq",
                    data={
                        "message": "Please ask a question."
                    },
                )

            answer = tool.execute(question)

            return ToolResult(
                success=True,
                tool="faq",
                data={
                    "answer": answer,
                },
            )

        # ----------------------------------------------------
        # COMPLAINT
        # ----------------------------------------------------

        if intent == Intent.COMPLAINT:
            try:
                data = tool.execute(
                    booking_code=booking_code,
                    complaint=question,
                    user_id=user_id,
                )
                return ToolResult(
                    success=True,
                    tool="complaint",
                    data=data,
                )
            except Exception as e:
                self.db.rollback()
                return ToolResult(
                    success=False,
                    tool="complaint",
                    data={"error": str(e), "message": "Failed to register complaint."},
                )

        # ----------------------------------------------------
        # Booking / Delay / Refund / Cancellation / Tracking / Payment / Reschedule
        # ----------------------------------------------------

        try:
            if intent == Intent.BOOKING_CANCEL:
                data = tool.execute(
                    booking_code=booking_code,
                    confirmation=confirmation,
                    user_id=user_id,
                )
            elif intent in (Intent.BOOKING_STATUS, Intent.REFUND_STATUS, Intent.PAYMENT_ISSUE, Intent.RESCHEDULE, Intent.BUS_TRACKING, Intent.BUS_DELAY):
                # Pass user_id for authorization checks
                data = tool.execute(
                    booking_code=booking_code,
                    user_id=user_id,
                )
            else:
                data = tool.execute(booking_code)
                
            return ToolResult(
                success=True,
                tool=intent.value.lower(),
                data=data,
            )
        except Exception as e:
            self.db.rollback()
            return ToolResult(
                success=False,
                tool=intent.value.lower(),
                data={
                    "booking_code": booking_code,
                    "found": False,
                    "error": str(e),
                    "message": f"No booking found or you do not have permission to view it for code {booking_code}."
                },
            )