from app.ai.intent.schemas import Intent


def route_intent(state):

    intent = state["intent"]

    routes = {
        Intent.BOOKING_STATUS: "booking_tool",
        Intent.BUS_DELAY: "delay_tool",
        Intent.CANCEL_BOOKING: "cancel_tool",
        Intent.REFUND: "refund_tool",
        Intent.COMPLAINT: "complaint_tool",
        Intent.FAQ: "faq_tool",
        Intent.GENERAL: "chat_node",
    }

    return routes.get(intent, "chat_node")