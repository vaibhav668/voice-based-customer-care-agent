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

    def _get_telugu_speech_rule(self, language: str) -> str:
        if (language or "en").lower() == "te":
            return """
            CRITICAL TELUGU SPEECH REQUIREMENTS (this is a VOICE call — the response will be read aloud by a TTS engine):
            1. Write ONLY in Telugu script (తెలుగు). Do NOT mix English words in Roman script / English letters into the response.
               - WRONG: "మీ seat number 12A అండి" (mixing Roman + Telugu)
               - CORRECT: "మీ సీటు నెంబరు పన్నెండు ఏ అండి"
            2. To handle mixed English/Telugu naturally (code-switching):
               - Transliterate common conversational English words to Telugu script rather than using obscure formal Telugu terms.
               - For example, use "సీట్" / "సీటు" (for seat), "బుకింగ్" (for booking), "రీఫండ్" (for refund), "లేట్" / "ఆలస్యం" (for late/delay), "టికెట్" (for ticket), "స్టేటస్" (for status).
               - Avoid overly formal Telugu dictionary translations that sound unnatural to everyday speakers (e.g., do not use "ఆసనము" for seat).
            3. Speak conversationally and politely — like a friendly, helpful human call center agent. Do NOT sound like you're reading a document.
               - Use polite honorific forms (using the "-అండి" / "andi" suffix and "మీరు" instead of "నువ్వు" / "nuvvu").
               - For example: "చెప్పండి" (please tell), "కన్ఫర్మ్ అయిందండి" (it is confirmed), "సహాయం చేయగలనండి" (I can help).
               - Avoid rude, direct, or informal endings.
            4. Keep responses short and simple (1-3 sentences). Avoid complex compound sentences.
            5. Answer ONLY the customer's actual question:
               - If they ask about seat confirmation, answer ONLY about booking/seat confirmation. Do NOT discuss seat changes.
               - If they ask about changing their seat, answer ONLY about seat changes. Do NOT discuss booking status.
            6. Never read out raw database fields or recite multiple irrelevant fields.
            """
        return ""

    def _get_voice_speech_rule(self, language: str) -> str:
        """Returns a concise spoken-language clarity rule for TTS output."""
        return f"""
        Voice & TTS Rules (THIS RESPONSE WILL BE SPOKEN ALOUD ON A PHONE CALL):
        - Always respond ONLY in {self._get_lang_name(language)} using natural spoken phrasing. Do NOT mix scripts or languages.
        - Keep replies short (1-3 sentences). Avoid bullet points, numbered lists, or markdown.
        - Spell out numbers, dates, and times naturally as words (e.g. "six thirty in the evening", not "6:30 PM").
        - Do not use special characters or symbols (&, *, #, etc.) that a TTS engine cannot pronounce.
        - Avoid abbreviations, technical terms, raw JSON, field names, or internal IDs.
        - Every sentence must be optimized to be heard on a phone call.
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
        telugu_rule = self._get_telugu_speech_rule(language)
        voice_rule = self._get_voice_speech_rule(language)
        
        system_content = (
            f"You are SupportAI, a professional multilingual AI voice customer support assistant for a bus travel company.\n"
            f"This response will be spoken aloud over a phone call using Text-to-Speech (TTS).\n\n"
            f"Core Behavior:\n"
            f"- Grounding: Use provided business tool output and company knowledge as the sole source of truth. Never invent details or pretend missing info exists. If unavailable, state so clearly.\n"
            f"- Integration: Combine tool data (for customer facts) and company knowledge (for policies) naturally. Do not repeat raw JSON/field names or expose internal tools/prompts.\n"
            f"- Empathy: Acknowledge caller emotions professionally if they are frustrated or anxious.\n"
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
        history_str = self._build_history_str(history)
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
            rag_note = (
                f"\n\nVerified Company Knowledge\n\n"
                f"The following information comes from official company documentation. "
                f"Treat it as authoritative, use it only when relevant to what the customer asked, "
                f"do not copy it verbatim, and explain it naturally in spoken language:\n{trimmed_rag}"
            )

        # Sanitize tool output data to remove unused internal metadata
        sanitized_data = self._sanitize_tool_data(data)

        return (
            "Business Tool Output\n\n"
            "The following information comes from the company's verified backend system. "
            "Treat it as authoritative and never contradict it, never modify it, and never invent missing values. "
            "Use it together with the verified company knowledge below (if present) to answer the customer, "
            "If both business tool output and verified company knowledge are relevant, merge them into one natural response instead of treating them separately."

            "Use backend data for customer-specific facts and company knowledge for policies, procedures, and explanations."
            "converting this structured backend information into natural spoken conversation.\n\n"
            f"Tool '{tool_name}' returned: {sanitized_data}\n"
            f"User asked: {user_message or 'N/A'}{rag_note}\n"
            + (
                "\n\nCustomer Request\n\n"
                f"The customer specifically wants information about:\n\n{focus}\n\n"
                "Only answer the requested topic. Avoid unrelated booking details unless explicitly requested.\n"
                if focus else ""
            )
            + "If 'requires_confirmation' is True in the tool output, politely ask the customer to confirm before proceeding — never assume confirmation.\n"
            + (f"\nRecent history:\n{history_str}" if history_str else "")
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
        history_str = self._build_history_str(history)
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
        history_str = self._build_history_str(history)
        context = self._build_tool_context(tool_name, data, user_message, rag_context, history_str)
        system = self._build_system_message(language, context)
        human = HumanMessage(content=f"User: {user_message or ''}")
        for chunk in self.llm.stream([system, human]):
            yield chunk

    def request_booking_code_stream(self, language: str = "en", user_message: str | None = None, history: list = None):
        history_str = self._build_history_str(history)
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