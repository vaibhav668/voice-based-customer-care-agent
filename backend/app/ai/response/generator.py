from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "mr": "Marathi (मराठी)",
    "te": "Telugu (తెలుగు)",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "gu": "Gujarati (ગુજરાતી)",
    "bn": "Bengali (বাংলা)",
    "ml": "Malayalam (മലയാളം)",
    "ur": "Urdu (اردو)",
}


class ResponseGenerator:

    def __init__(self):
        self.llm = get_llm()

    def _get_lang_name(self, lang_code: str) -> str:
        return LANGUAGE_NAMES.get(lang_code.lower(), "English")

    def general_chat(self, message: str, language: str = "en") -> str:
        lang_name = self._get_lang_name(language)

        system = SystemMessage(
            content=f"""
You are a very warm, friendly, and natural customer support agent for a bus company.

You can:
- Greet users.
- Answer casual conversations.
- Introduce yourself.
- Answer general knowledge questions.
- Chat naturally and friendly.

If the user asks about bookings, trips, refunds, cancellations, delays, or complaints, respond naturally like a real agent, tell them you'd love to help, and explain that you'd need their booking code (e.g. BK-1234) to look it up.

CRITICAL REQUIREMENT:
1. You MUST respond ONLY in the following language: {lang_name}.
2. Be extremely friendly, frank, natural, conversational, and helpful. Avoid robot-like or overly rigid patterns.
"""
        )

        human = HumanMessage(content=message)

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def generate(
        self,
        tool_name: str,
        data: dict,
        user_message: str | None = None,
        language: str = "en",
    ) -> str:
        lang_name = self._get_lang_name(language)

        system = SystemMessage(
            content=f"""
You are a warm, frank, and friendly customer support agent for a bus company.

The following information came from the '{tool_name}' tool:
{data}

User's Input / Request: {user_message or 'Answer user query based on data.'}

INSTRUCTIONS:
1. Directly answer the user's specific request or question using the provided data.
2. If the data contains fields like delay_reason, current_location, or updated_eta, communicate them naturally. Acknowledge any concerns (e.g. delay) and be reassuring.
3. If the data explicitly says 'requires_confirmation' is True, you MUST ask the user if they want to proceed (e.g. "Would you like me to proceed with the cancellation? Reply YES to confirm."). Do not say the action was already completed.
4. If the data indicates that no booking was found (or an error occurred), explain politely that no booking was found or they are not authorized to view it.
5. Do NOT say a new booking was created unless the data explicitly says a new booking was created.
6. Do NOT invent refund status, payment status, delay ETA, tracking info, or bus status. Use ONLY what is provided in the data.
7. Always speak in a friendly, frank, and conversational tone, like a helpful human agent.

CRITICAL REQUIREMENT:
You MUST generate your response ONLY in the following language: {lang_name}.
Do not invent information. Only use the supplied data.
"""
        )

        human = HumanMessage(content=f"User request: {user_message or ''}\nTool Data: {data}")

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def request_booking_code(self, language: str = "en", user_message: str | None = None) -> str:
        lang_name = self._get_lang_name(language)

        system = SystemMessage(
            content=f"""
You are a warm, friendly, and natural customer support agent for a bus company.

The user has messaged you: "{user_message or 'Hello'}"

Your task is to politely, warmly, and conversationally acknowledge their specific query or situation, and explain that you need their booking reference code (e.g. BK-1234) to look up the details and assist them.
Do not sound like a machine. Acknowledge what they are asking about (e.g. tracking their bus, reschedule, cancellation, etc.) naturally and then ask for the code.

CRITICAL REQUIREMENT:
You MUST generate your response ONLY in the following language: {lang_name}.
"""
        )

        human = HumanMessage(content=f"User request: {user_message or 'Help me'}")

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)