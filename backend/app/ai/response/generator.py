from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm
from app.ai.utils.shared_prompts import HINDI_FEMININE_RULE, TELUGU_SPEECH_RULE, VOICE_TTS_RULE


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
            return HINDI_FEMININE_RULE
        return ""

    def _get_telugu_speech_rule(self, language: str) -> str:
        if (language or "en").lower() == "te":
            return TELUGU_SPEECH_RULE
        return ""

    def _get_voice_speech_rule(self, language: str) -> str:
        """Returns a concise spoken-language clarity rule for TTS output."""
        lang_name = self._get_lang_name(language)
        return VOICE_TTS_RULE.format(lang_name=lang_name)

    def _build_history_str(self, history: list | None, tool_name: str | None = None, user_message: str | None = None, turns: int = 3) -> str:
        if not history:
            return ""
        from app.ai.utils.shared_prompts import select_relevant_history
        relevant = select_relevant_history(history, tool_name, user_message, turns)
        return "\n".join(
            f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
            for msg in relevant
        )

    def _build_system_message(self, language: str, context_body: str) -> SystemMessage:
        """Builds a compact system message with shared language/voice rules."""
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        telugu_rule = self._get_telugu_speech_rule(language)
        voice_rule = self._get_voice_speech_rule(language)
        
        system_content = (
            f"You are SupportAI, a premium, professional, and empathetic multilingual AI voice customer support executive for a bus travel company.\n"
            f"This response will be spoken aloud over a phone call using Text-to-Speech (TTS).\n\n"
            f"Core Behavior:\n"
            f"- Persona: Act like a premium, friendly customer support agent. Validate customer feelings, offer polite greetings/acknowledgement, and maintain warm, professional customer care tone.\n"
            f"- Grounding: Use provided business tool output and company knowledge as the sole source of truth. Never invent details or pretend missing info exists. If unavailable, state so clearly.\n"
            f"- Speech Integration: Translate structured backend dictionary fields/statuses (like CONFIRMED, COMPLETED, CANCELLED) into natural conversational sentences. Seamlessly blend backend facts and company policies into a single cohesive response.\n"
            f"- Comprehensiveness: Address every single question asked by the customer in their query. Do not skip any part of their request.\n"
            f"- Directness & Style: Prioritize the user's intent and answer their question or fulfill their request immediately. Do not prepend responses with unnecessary introductory context (such as summarizing what they asked, stating 'Let me answer your question...', or referencing 'According to your booking...'). Do not automatically recite booking details or customer info unless directly requested.\n"
            f"- Flow: Maintain context from recent history below. Never repeat information already given unless asked again.\n"
            f"- Endings: Ask exactly one follow-up question if more info is needed.\n\n"
            f"{voice_rule.strip()}\n"
        )
        
        if hindi_rule.strip():
            system_content += f"\n{hindi_rule.strip()}\n"
        if telugu_rule.strip():
            system_content += f"\n{telugu_rule.strip()}\n"
            
        system_content += f"\n{context_body}"
        return SystemMessage(content=system_content)

    def general_chat(self, message: str, language: str = "en", history: list = None) -> str:
        history_str = self._build_history_str(history, "chat", message)
        context = (
            "Conversation Mode: General Chat\n\n"
            "Behave like a friendly, approachable customer support executive having a natural phone conversation. "
            "Greet users warmly, answer general questions, and keep the conversation flowing naturally — do not sound scripted or robotic. "
            "Never invent customer-specific information such as booking details, refund status, or payment status; you do not have access to any of that until the customer provides a booking reference. "
            "If the user asks about bookings, refunds, or cancellations, politely explain that you'll need their booking reference code (e.g. BK-1234) to look into it, only asking for it if you don't already have it from the conversation history below.\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)

        human = HumanMessage(content=message)

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def _sanitize_tool_data(self, data: dict) -> dict:
        """Recursively removes internal IDs, timestamps, and unused metadata to minimize tokens."""
        if not isinstance(data, dict):
            return data
        exclude_keys = {
            "id", "user_id", "created_at", "updated_at", "session_id", "session_phone", "db_id"
        }
        sanitized = {}
        for k, v in data.items():
            if k in exclude_keys:
                continue
            if isinstance(v, dict):
                sanitized[k] = self._sanitize_tool_data(v)
            elif isinstance(v, list):
                sanitized[k] = [self._sanitize_tool_data(item) if isinstance(item, dict) else item for item in v]
            else:
                sanitized[k] = v
        return sanitized

    def _build_tool_context(self, tool_name: str, data: dict, user_message: str | None, rag_context: str | None, history_str: str) -> str:
        """Builds the focused tool-call context body, dynamically injecting only relevant parts."""
        tool_lower = (tool_name or "").lower()
        
        # 1. Determine injection flags based on query/tool type
        inject_tool_data = True
        inject_rag = False

        if tool_lower in ("chat", "general"):
            inject_tool_data = False
            inject_rag = False
        elif tool_lower == "faq":
            inject_tool_data = False
            inject_rag = True
        elif "refund" in tool_lower or "payment" in tool_lower:
            inject_tool_data = True
            inject_rag = True
        elif "booking" in tool_lower or "trip" in tool_lower:
            inject_tool_data = True
            inject_rag = False
        elif "cancel" in tool_lower or "reschedule" in tool_lower:
            inject_tool_data = True
            inject_rag = True
        else:
            inject_tool_data = True
            inject_rag = bool(rag_context)

        # 2. Build target response focus instructions
        focus = ""
        if "refund" in tool_lower:
            focus = "State ONLY the refund status/timeline. Do NOT mention departure, arrival, seat, route."
        elif "delay" in tool_lower or "tracking" in tool_lower:
            focus = "State ONLY whether bus is delayed, current location, and updated ETA. Do NOT mention payment or refund."
        elif "booking" in tool_lower or "status" in tool_lower:
            focus = "Answer ONLY the specific field the user asked about (e.g. arrival time, departure, seat, destination). Do NOT recite all fields."

        context_parts = []

        if inject_tool_data and data:
            sanitized_data = self._sanitize_tool_data(data)
            if sanitized_data:
                tool_section = (
                    "Business Tool Output\n"
                    "Information from verified backend system. Treat as authoritative.\n"
                    f"Tool '{tool_name}' returned: {sanitized_data}"
                )
                context_parts.append(tool_section)

        if inject_rag and rag_context:
            trimmed_rag = rag_context[:500].rstrip() + ("..." if len(rag_context) > 500 else "")
            rag_section = (
                "Verified Company Knowledge (FAQ/Policy)\n"
                "Information from official company documentation. Explain naturally in spoken language:\n"
                f"{trimmed_rag}"
            )
            context_parts.append(rag_section)

        if focus:
            focus_section = (
                "Customer Request Focus\n"
                f"The customer specifically wants information about: {focus}\n"
                "Only answer the requested topic. Avoid unrelated booking details unless explicitly requested."
            )
            context_parts.append(focus_section)

        if data and isinstance(data, dict) and data.get("requires_confirmation"):
            context_parts.append("If 'requires_confirmation' is True in the tool output, politely ask the customer to confirm before proceeding.")

        if history_str:
            context_parts.append(f"Recent conversation history:\n{history_str}")

        return "\n\n".join(context_parts)

    def generate(
        self,
        tool_name: str,
        data: dict,
        user_message: str | None = None,
        language: str = "en",
        rag_context: str | None = None,
        history: list = None,
    ) -> str:
        history_str = self._build_history_str(history, tool_name, user_message)
        context = self._build_tool_context(tool_name, data, user_message, rag_context, history_str)
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or ''}")
        response = self.llm.invoke([system, human])
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response)

    def request_booking_code(self, language: str = "en", user_message: str | None = None, history: list = None) -> str:
        history_str = self._build_history_str(history, "booking", user_message)
        context = (
            f"The user said: \"{user_message or 'Hello'}\"\n\n"
            "Warmly acknowledge what the customer just asked, briefly explain that you need their booking reference "
            "code to look up their specific booking details, and then politely ask them for it. "
            "Give a natural example of the format, such as BK-1234. "
            "Check the recent history below first — if the customer has already given a booking reference in this "
            "conversation, do not ask for it again; instead, acknowledge it and proceed naturally. "
            "Keep the tone conversational and warm, not like a form request.\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or 'Help me'}")
        response = self.llm.invoke([system, human])
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response)

    def general_chat_stream(self, message: str, language: str = "en", history: list = None):
        history_str = self._build_history_str(history, "chat", message)
        context = (
            "Conversation Mode: General Chat\n\n"
            "Behave like a friendly, approachable customer support executive having a natural phone conversation. "
            "Greet users warmly, answer general questions, and keep the conversation flowing naturally — do not sound scripted or robotic. "
            "Never invent customer-specific information such as booking details, refund status, or payment status; you do not have access to any of that until the customer provides a booking reference. "
            "If the user asks about bookings, refunds, or cancellations, politely explain that you'll need their booking reference code (e.g. BK-1234) to look into it, only asking for it if you don't already have it from the conversation history below.\n"
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
        history_str = self._build_history_str(history, tool_name, user_message)
        context = self._build_tool_context(tool_name, data, user_message, rag_context, history_str)
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or ''}")
        for chunk in self.llm.stream([system, human]):
            yield chunk

    def request_booking_code_stream(self, language: str = "en", user_message: str | None = None, history: list = None):
        history_str = self._build_history_str(history, "booking", user_message)
        context = (
            f"The user said: \"{user_message or 'Hello'}\"\n\n"
            "Warmly acknowledge what the customer just asked, briefly explain that you need their booking reference "
            "code to look up their specific booking details, and then politely ask them for it. "
            "Give a natural example of the format, such as BK-1234. "
            "Check the recent history below first — if the customer has already given a booking reference in this "
            "conversation, do not ask for it again; instead, acknowledge it and proceed naturally. "
            "Keep the tone conversational and warm, not like a form request.\n"
            + (f"Recent history:\n{history_str}" if history_str else "")
        )
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or 'Help me'}")
        for chunk in self.llm.stream([system, human]):
            yield chunk