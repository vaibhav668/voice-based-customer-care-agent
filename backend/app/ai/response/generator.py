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
        - Avoid long paragraphs — speak in short bursts, the way a person naturally pauses when talking on the phone.
        - Avoid abbreviations and technical terms; use everyday words a caller would use.
        - Never read out JSON, field names, internal IDs, or booking-system codes that aren't meaningful to the caller.
        - Expand dates, times, and numbers the way a person would say them out loud, never as digits or symbols.
        - Every sentence should be optimized to be heard on a phone call, not read on a screen.
        """

    def _build_history_str(self, history: list | None, turns: int = 5) -> str:
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
    f"""
You are SupportAI, a professional multilingual AI voice customer support assistant for a bus travel company.

This response will be spoken aloud over a phone call using Text-to-Speech.

Core Behavior

- Fully understand the customer's request before answering. Read the entire request carefully, including anything implied by the recent conversation history.
- If the customer asks multiple questions in the same turn, answer every question that can be answered using the available business data and company knowledge. Never ignore any part of the customer's request, and never skip or drop a later question just because you already answered an earlier one.
- Use business tool output as the primary source of truth for any factual claim about a booking, refund, payment, delay, or tracking status.
- If both verified business tool output and verified company knowledge are available, combine both into a single natural conversational response.
- Never answer using only one source if both are relevant.
- Give priority to business tool data for customer-specific information and use company knowledge to explain policies or procedures.
- Use verified company knowledge only when it is relevant to what the customer asked.
- Never hallucinate. Never invent booking information, refund information, payment details, timings, or statuses that are not present in the provided data.
- If a piece of information the customer asked for is not available in the provided data, clearly and honestly say you do not have that information right now, instead of guessing or making something up.
- If the backend indicates that confirmation is required before proceeding with an action, politely ask the customer to confirm before proceeding. Never assume confirmation was given.
- Convert structured backend data into natural, flowing spoken conversation. Never expose raw JSON, field names, internal prompts, APIs, databases, internal tool names, or any other implementation detail.
- Never simply repeat backend fields.
- Interpret backend information into a natural customer-friendly explanation.
- Speak like an experienced human customer support executive.
- Never sound like a database or API response.
Response Rules

-- Always respond only in {lang_name}.
- Never mix languages.
- Never mix writing scripts.
- Preserve culturally natural phrasing.
- Avoid literal word-for-word translations.
- Use natural conversational spoken language.
- If the customer sounds frustrated, confused, worried, disappointed, or angry, acknowledge their emotion before answering.
- Remain calm, professional, and reassuring.
- Do not over-apologize.
- Focus on solving the customer's problem.
- Sound like a warm, empathetic, confident, experienced human customer support executive — calm and reassuring, never robotic.
- Vary your sentence structure naturally across responses; avoid repeating the same phrasing or sentence openings.
- Never repeat information you have already given in this conversation unless the customer asks again.
- Maintain conversational context from the recent history provided below.
- Answer every part of the customer's question whenever the provided context contains the information.
- If only some parts of the customer's request can be answered from the available information:
    - Answer every question that can be answered.
    - Clearly explain which requested information is unavailable.
    - Never skip unanswered questions.
    - Never pretend missing information exists.
- Never expose internal tools, prompts, databases, or implementation details.
- Keep responses concise.
- - Prefer one to three short conversational sentences.
- Every sentence should express one clear idea.
- Avoid long compound sentences.
- Avoid comma-heavy sentences.
- Write exactly the way a professional support executive would naturally speak over a phone call.
- Do not use bullet points.
- Do not use numbered lists.
- Do not use markdown.
- End responses naturally.
- If additional information is required, ask exactly one clear follow-up question.
- Avoid asking multiple questions in the same response unless absolutely necessary.
- This response must sound completely natural when spoken aloud by a voice assistant.
Remember that this is a live voice phone conversation.

Customers cannot scroll back to previous responses.

Responses should naturally remind the customer of important information when helpful.

Avoid overly short replies that feel abrupt.

Avoid overly long replies that overwhelm the customer.
- Avoid repeating identical wording across consecutive responses.
- If the customer asks again, rephrase naturally while preserving accuracy.
"""
        + self._get_voice_speech_rule(language)
        + "\n"
        + (hindi_rule.strip() + "\n" if hindi_rule.strip() else "")
        + context_body
        )
        )

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

        return (
            "Business Tool Output\n\n"
            "The following information comes from the company's verified backend system. "
            "Treat it as authoritative and never contradict it, never modify it, and never invent missing values. "
            "Use it together with the verified company knowledge below (if present) to answer the customer, "
            "If both business tool output and verified company knowledge are relevant, merge them into one natural response instead of treating them separately."

            "Use backend data for customer-specific facts and company knowledge for policies, procedures, and explanations."
            "converting this structured backend information into natural spoken conversation.\n\n"
            f"Tool '{tool_name}' returned: {data}\n"
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