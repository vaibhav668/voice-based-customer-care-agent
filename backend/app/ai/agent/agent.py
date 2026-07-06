from sqlalchemy.orm import Session

from app.ai.schemas.tool_result import ToolResult
from app.ai.tools.registry import ToolRegistry
from app.ai.intent.schemas import Intent

class SupportAgent:

    def __init__(self, db: Session):
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
        user_id=None,
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
            Intent.BOOKING_CANCEL,
            Intent.REFUND_STATUS,
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
                return ToolResult(
                    success=False,
                    tool="create_booking",
                    data={"error": str(e), "message": "Failed to create booking."},
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
        # Booking / Delay / Refund / Cancellation
        # ----------------------------------------------------

        try:
            data = tool.execute(booking_code)
            return ToolResult(
                success=True,
                tool=intent.value.lower(),
                data=data,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool=intent.value.lower(),
                data={
                    "booking_code": booking_code,
                    "found": False,
                    "error": str(e),
                    "message": f"No booking found for booking code {booking_code}."
                },
            )