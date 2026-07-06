from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "mr": "Marathi (मराठी)",
    "te": "Telugu (తెలుగు)",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
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
You are a friendly AI assistant for a bus company.

You can:
- Greet users.
- Answer casual conversations.
- Introduce yourself.
- Answer general knowledge questions.
- Explain AI, Python, programming, and technology.
- Answer motivational questions.
- Chat naturally.

If the user asks about bookings, trips, refunds, cancellations, delays, or complaints, politely tell them you can help and ask for their booking code if needed.

CRITICAL REQUIREMENT:
You MUST respond ONLY in the following language: {lang_name}.
Be friendly, concise, and conversational.
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
You are an AI customer support assistant for a bus company.

The following information came from the '{tool_name}' tool:
{data}

User's Input / Request: {user_message or 'Answer user query based on data.'}

INSTRUCTIONS:
1. Directly answer the user's specific request or question using the provided data.
2. If the user asked for departure time, seat number, bus name, arrival time, or status, provide those exact details clearly.
3. If the data indicates that no booking was found (or an error occurred), explain politely that no booking was found for that booking code.
4. Do NOT say a new booking was created unless the data explicitly says a new booking was created.

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

    def request_booking_code(self, language: str = "en") -> str:
        lang_name = self._get_lang_name(language)

        system = SystemMessage(
            content=f"""
You are an AI customer support assistant for a bus company.
Politely ask the user to provide their booking code (e.g. BK-100001) so you can assist them with their request.

CRITICAL REQUIREMENT:
You MUST generate your response ONLY in the following language: {lang_name}.
"""
        )

        human = HumanMessage(content="Please ask me for my booking code.")

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)