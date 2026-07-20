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
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
}


class ResponseGenerator:

    def __init__(self):
        self.llm = get_llm()

    def _get_lang_name(self, lang_code: str) -> str:
        return LANGUAGE_NAMES.get(lang_code.lower(), "English")

    def _get_hindi_feminine_rule(self, language: str) -> str:
        if (language or "en").lower() == "hi":
            return """
            CRITICAL HINDI SPEECH REQUIREMENTS (this is a VOICE call — the response will be read aloud by a TTS engine):
            1. Write ONLY in Devanagari script (हिंदी). Do NOT mix English words or Roman script into the response.
               - WRONG: "Aapka arrival time 6:30 PM hai" (mixing Roman + Devanagari)
               - CORRECT: "आपका आगमन का समय शाम छह बजकर तीस मिनट है"
            2. Since the assistant voice is FEMALE, ALWAYS use feminine grammatical structures:
               - Use "करूंगी" not "करूंगा", "सकती हूं" not "सकता हूं", "बताऊंगी" not "बताऊंगा".
            3. Speak conversationally — like a friendly human call center agent. Do NOT sound like you're reading a document.
               - Short, warm, clear sentences. No bullet points or formal lists.
            4. Never use awkward formal Sanskrit-heavy words when simpler Hindi exists. Prefer everyday spoken Hindi.
            """
        return ""

    def _get_voice_speech_rule(self, language: str) -> str:
        """Returns a spoken-language clarity rule for TTS output in any language."""
        return f"""
        IMPORTANT — THIS RESPONSE WILL BE SPOKEN ALOUD ON A PHONE CALL:
        - Write in natural spoken {self._get_lang_name(language)} only. Do NOT mix scripts or languages.
        - Use short, conversational sentences. Avoid bullet points, numbered lists, or formal document-style prose.
        - Spell out numbers and times naturally as words (e.g. "six thirty in the evening", not "6:30 PM").
        - Do not use special characters or symbols (&, *, #, etc.) that a TTS engine cannot pronounce.
        """

    def _build_history_str(self, history: list | None, turns: int = 3) -> str:
        if not history:
            return ""
        return "\n".join(
            f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
            for msg in history[-turns:]
        )

    def _build_system_message(self, language: str, context_body: str) -> SystemMessage:
        """Builds a compact system message with shared language/voice rules."""
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        return SystemMessage(
            content=(
                f"You are a professional bus company customer support agent.\n"
                f"Respond ONLY in {lang_name}. Be warm, concise (1-2 spoken sentences max). "
                f"Never sound robotic. Do not invent information. "
                f"Do not use bullet points or lists — this will be spoken aloud via TTS.\n"
                + (hindi_rule.strip() + "\n" if hindi_rule.strip() else "")
                + context_body
            )
        )

    def general_chat(self, message: str, language: str = "en", history: list = None) -> str:
        history_str = self._build_history_str(history)
        context = (
            "You can greet users, answer general questions, and chat naturally. "
            "If the user asks about bookings/refunds/cancellations, explain you need their booking code (e.g. BK-1234).\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)

        human = HumanMessage(content=message)

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def _build_tool_context(self, tool_name: str, data: dict, user_message: str | None, rag_context: str | None, history_str: str) -> str:
        """Builds the focused tool-call context body, trimming to essential fields."""
        tool_lower = (tool_name or "").lower()
        focus = ""
        if "refund" in tool_lower:
            focus = "State ONLY the refund status/timeline. Do NOT mention departure, arrival, seat, route."
        elif "delay" in tool_lower:
            focus = "State ONLY whether bus is delayed and updated ETA. Do NOT mention payment or refund."
        elif "tracking" in tool_lower:
            focus = "State ONLY the current bus location/tracking status."
        elif "booking" in tool_lower or "status" in tool_lower:
            focus = (
                "Answer ONLY the specific field the user asked about (e.g. arrival time, departure, seat, destination). "
                "Do NOT recite all fields."
            )

        rag_note = ""
        if rag_context:
            # Trim RAG context to first 500 chars to limit token usage
            trimmed_rag = rag_context[:500].rstrip() + ("..." if len(rag_context) > 500 else "")
            rag_note = f"\nPolicy context: {trimmed_rag}"

        return (
            f"Tool '{tool_name}' returned: {data}\n"
            f"User asked: {user_message or 'N/A'}{rag_note}\n"
            + (f"Focus: {focus}\n" if focus else "")
            + (f"If 'requires_confirmation' is True, ask user to confirm before proceeding.\n")
            + (f"Recent history:\n{history_str}" if history_str else "")
        )

    def generate(
        self,
        tool_name: str,
        data: dict,
        user_message: str | None = None,
        language: str = "en",
        rag_context: str | None = None,
        history: list = None,
    ) -> str:
        history_str = self._build_history_str(history)
        context = self._build_tool_context(tool_name, data, user_message, rag_context, history_str)
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or ''}")
        response = self.llm.invoke([system, human])
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response)

    def request_booking_code(self, language: str = "en", user_message: str | None = None, history: list = None) -> str:
        history_str = self._build_history_str(history)
        context = (
            f"The user said: \"{user_message or 'Hello'}\"\n"
            "Politely acknowledge their query and ask for their booking reference code (e.g. BK-1234) to look up details.\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or 'Help me'}")
        response = self.llm.invoke([system, human])
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response)

    def general_chat_stream(self, message: str, language: str = "en", history: list = None):
        history_str = self._build_history_str(history)
        context = (
            "You can greet users, answer general questions, and chat naturally. "
            "If the user asks about bookings/refunds/cancellations, explain you need their booking code (e.g. BK-1234).\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)
        human = HumanMessage(content=message)
        for chunk in self.llm.stream([system, human]):
            yield chunk

    def generate_stream(
        self,
        tool_name: str,
        data: dict,
        user_message: str | None = None,
        language: str = "en",
        rag_context: str | None = None,
        history: list = None,
    ):
        history_str = self._build_history_str(history)
        context = self._build_tool_context(tool_name, data, user_message, rag_context, history_str)
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or ''}")
        for chunk in self.llm.stream([system, human]):
            yield chunk

    def request_booking_code_stream(self, language: str = "en", user_message: str | None = None, history: list = None):
        history_str = self._build_history_str(history)
        context = (
            f"The user said: \"{user_message or 'Hello'}\"\n"
            "Politely acknowledge their query and ask for their booking reference code (e.g. BK-1234) to look up details.\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or 'Help me'}")
        for chunk in self.llm.stream([system, human]):
            yield chunk