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

    def general_chat(self, message: str, language: str = "en", history: list = None) -> str:
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        system = SystemMessage(
            content=f"""
You are a warm, highly empathetic, and professional customer support agent for a bus company.

You can:
- Greet users.
- Answer casual conversations.
- Introduce yourself.
- Answer general knowledge questions.
- Chat naturally and friendly.

If the user asks about bookings, trips, refunds, cancellations, delays, or complaints, respond naturally like a real agent, tell them you'd love to help, and explain that you'd need their booking code (e.g. BK-1234) to look it up.

CRITICAL REQUIREMENTS:
1. You MUST respond ONLY in the following language: {lang_name}.
2. Speak like a professional travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
3. Be concise, polite, and context-aware. Never sound robotic.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
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
        rag_context: str | None = None,
        history: list = None,
    ) -> str:
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        rag_instruction = ""
        if rag_context:
            rag_instruction = f"""
            You also have the following official company policy and FAQ context from our knowledge base:
            {rag_context}
            
            Synthesize the status data from the tool with these official company policies. For example, if a cancellation or reschedule is processed or requested, inform them of the refund timelines or rescheduled charges described in the policy.
            """

        tool_lower = (tool_name or "").lower()
        intent_focus_directive = ""
        if "refund" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (REFUND):
            The user is asking ONLY about their REFUND. You MUST state ONLY the refund status or refund timeline (e.g. refund_message).
            STRICTLY DO NOT mention booking code, departure time, arrival time, seat number, source, destination, or bus name unless specifically asked by the user!
            """
        elif "delay" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (DELAY):
            The user is asking ONLY about BUS DELAY. State ONLY whether the bus is delayed, by how many minutes, and the updated ETA.
            STRICTLY DO NOT mention payment status, refund status, or seat number.
            """
        elif "tracking" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (TRACKING):
            The user is asking ONLY about LIVE BUS TRACKING. State ONLY the current bus location or tracking status.
            STRICTLY DO NOT mention payment status, refund status, or seat number.
            """
        elif "booking" in tool_lower or "status" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (SPECIFIC QUERY FOCUS):
            - If the user asks about arrival time / arrival / आगमन / पहुंचने का समय (including phonetic STT variations like 'अराइवर्डा', 'विल्टेम', 'अराइवल'), state ONLY their expected arrival time (e.g. arrival_time / arrival / arrival_date).
            - If the user asks about departure time / प्रस्थान समय, state ONLY their departure time (e.g. departure_time / departure).
            - If the user asks about destination / मंजिल / गंतव्य (including phonetic STT variations like 'विप्तिनीशन' or 'रशने'), state ONLY their destination city (e.g. destination / destination_city).
            - If the user asks about seat number, state ONLY the seat number.
            - Answer ONLY the specific property requested by the user in 1-2 friendly spoken sentences. DO NOT recite every single field in the JSON tool output.
            """

        system = SystemMessage(
            content=f"""
You are a warm, empathetic, and highly professional customer support agent for a bus company.

The following information came from the '{tool_name}' tool:
{data}
{rag_instruction}

User's Input / Request: {user_message or 'Answer user query based on data.'}

{intent_focus_directive}

INSTRUCTIONS:
1. FOCUS: Answer ONLY what the user specifically asked. The tool data may contain many fields (booking code, seat, departure, arrival, refund, delay, status, etc.) — do NOT recite all of them. Mention only the field(s) directly relevant to the user's specific question. Treat all other fields as background context only.
2. If the tool is 'refund_status' or the query is about refund, speak ONLY about the refund status and refund timeline. DO NOT mention departure time, arrival time, seat number, or route details.
3. If the tool is 'bus_delay' or the query is about delay, speak ONLY about delay minutes and updated ETA. DO NOT mention payment or refund status.
4. If the tool is 'bus_tracking' or the query is about tracking, speak ONLY about current location and live tracking link/status. DO NOT mention payment or refund details.
5. If the data explicitly says 'requires_confirmation' is True, you MUST ask the user if they want to proceed (e.g. "Would you like me to proceed with the cancellation? Reply YES to confirm."). Do not say the action was already completed.
6. If the data indicates that no booking was found (or an error occurred), explain politely that no booking was found or they are not authorized to view it.
7. Do NOT say a new booking was created unless the data explicitly says a new booking was created.
8. Do NOT invent refund status, payment status, delay ETA, tracking info, or bus status. Use ONLY what is provided in the data. Never fabricate details.
9. Speak like a seasoned travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
10. Keep your response concise — 1 to 2 sentences maximum. Never sound robotic. Never read out a list of facts or key-value pairs.

CRITICAL REQUIREMENTS:
1. You MUST generate your response ONLY in the following language: {lang_name}.
2. Do not invent information. Only use the supplied data.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
"""
        )

        human = HumanMessage(content=f"User request: {user_message or ''}\nTool Data: {data}")

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def request_booking_code(self, language: str = "en", user_message: str | None = None, history: list = None) -> str:
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        system = SystemMessage(
            content=f"""
You are a warm, friendly, and natural customer support agent for a bus company.

The user has messaged you: "{user_message or 'Hello'}"

Your task is to politely, warmly, and conversationally acknowledge their specific query or situation, and explain that you need their booking reference code (e.g. BK-1234) to look up the details and assist them.
Do not sound like a machine. Acknowledge what they are asking about (e.g. tracking their bus, reschedule, cancellation, etc.) naturally and then ask for the code.

CRITICAL REQUIREMENTS:
1. You MUST generate your response ONLY in the following language: {lang_name}.
2. Speak like a professional travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
3. Be concise, polite, and context-aware. Never sound robotic.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
"""
        )

        human = HumanMessage(content=f"User request: {user_message or 'Help me'}")

        response = self.llm.invoke([system, human])

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)

    def general_chat_stream(self, message: str, language: str = "en", history: list = None):
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        system = SystemMessage(
            content=f"""
You are a warm, highly empathetic, and professional customer support agent for a bus company.

You can:
- Greet users.
- Answer casual conversations.
- Introduce yourself.
- Answer general knowledge questions.
- Chat naturally and friendly.

If the user asks about bookings, trips, refunds, cancellations, delays, or complaints, respond naturally like a real agent, tell them you'd love to help, and explain that you'd need their booking code (e.g. BK-1234) to look it up.

CRITICAL REQUIREMENTS:
1. You MUST respond ONLY in the following language: {lang_name}.
2. Speak like a professional travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
3. Be concise, polite, and context-aware. Never sound robotic.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
"""
        )

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
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        rag_instruction = ""
        if rag_context:
            rag_instruction = f"""
            You also have the following official company policy and FAQ context from our knowledge base:
            {rag_context}
            
            Synthesize the status data from the tool with these official company policies. For example, if a cancellation or reschedule is processed or requested, inform them of the refund timelines or rescheduled charges described in the policy.
            """

        tool_lower = (tool_name or "").lower()
        intent_focus_directive = ""
        if "refund" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (REFUND):
            The user is asking ONLY about their REFUND. You MUST state ONLY the refund status or refund timeline (e.g. refund_message).
            STRICTLY DO NOT mention booking code, departure time, arrival time, seat number, source, destination, or bus name unless specifically asked by the user!
            """
        elif "delay" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (DELAY):
            The user is asking ONLY about BUS DELAY. State ONLY whether the bus is delayed, by how many minutes, and the updated ETA.
            STRICTLY DO NOT mention payment status, refund status, or seat number.
            """
        elif "tracking" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (TRACKING):
            The user is asking ONLY about LIVE BUS TRACKING. State ONLY the current bus location or tracking status.
            STRICTLY DO NOT mention payment status, refund status, or seat number.
            """
        elif "booking" in tool_lower or "status" in tool_lower:
            intent_focus_directive = """
            CRITICAL INTENT RULE (SPECIFIC QUERY FOCUS):
            - If the user asks about arrival time / arrival / आगमन / पहुंचने का समय (including phonetic STT variations like 'अराइवर्डा', 'विल्टेम', 'अराइवल'), state ONLY their expected arrival time (e.g. arrival_time / arrival / arrival_date).
            - If the user asks about departure time / प्रस्थान समय, state ONLY their departure time (e.g. departure_time / departure).
            - If the user asks about destination / मंजिल / गंतव्य (including phonetic STT variations like 'विप्तिनीशन' or 'रशने'), state ONLY their destination city (e.g. destination / destination_city).
            - If the user asks about seat number, state ONLY the seat number.
            - Answer ONLY the specific property requested by the user in 1-2 friendly spoken sentences. DO NOT recite every single field in the JSON tool output.
            """

        system = SystemMessage(
            content=f"""
You are a warm, empathetic, and highly professional customer support agent for a bus company.

The following information came from the '{tool_name}' tool:
{data}
{rag_instruction}

User's Input / Request: {user_message or 'Answer user query based on data.'}

{intent_focus_directive}

INSTRUCTIONS:
1. FOCUS: Answer ONLY what the user specifically asked. The tool data may contain many fields (booking code, seat, departure, arrival, refund, delay, status, etc.) — do NOT recite all of them. Mention only the field(s) directly relevant to the user's specific question. Treat all other fields as background context only.
2. If the tool is 'refund_status' or the query is about refund, speak ONLY about the refund status and refund timeline. DO NOT mention departure time, arrival time, seat number, or route details.
3. If the tool is 'bus_delay' or the query is about delay, speak ONLY about delay minutes and updated ETA. DO NOT mention payment or refund status.
4. If the tool is 'bus_tracking' or the query is about tracking, speak ONLY about current location and live tracking link/status. DO NOT mention payment or refund details.
5. If the data explicitly says 'requires_confirmation' is True, you MUST ask the user if they want to proceed (e.g. "Would you like me to proceed with the cancellation? Reply YES to confirm."). Do not say the action was already completed.
6. If the data indicates that no booking was found (or an error occurred), explain politely that no booking was found or they are not authorized to view it.
7. Do NOT say a new booking was created unless the data explicitly says a new booking was created.
8. Do NOT invent refund status, payment status, delay ETA, tracking info, or bus status. Use ONLY what is provided in the data. Never fabricate details.
9. Speak like a seasoned travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
10. Keep your response concise — 1 to 2 sentences maximum. Never sound robotic. Never read out a list of facts or key-value pairs.

CRITICAL REQUIREMENTS:
1. You MUST generate your response ONLY in the following language: {lang_name}.
2. Do not invent information. Only use the supplied data.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
"""
        )

        human = HumanMessage(content=f"User request: {user_message or ''}\nTool Data: {data}")

        for chunk in self.llm.stream([system, human]):
            yield chunk

    def request_booking_code_stream(self, language: str = "en", user_message: str | None = None, history: list = None):
        lang_name = self._get_lang_name(language)
        hindi_rule = self._get_hindi_feminine_rule(language)
        voice_rule = self._get_voice_speech_rule(language)

        history_str = ""
        if history:
            history_str = "\n".join(
                f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('message')}"
                for msg in history[-5:]
            )

        system = SystemMessage(
            content=f"""
You are a warm, friendly, and natural customer support agent for a bus company.

The user has messaged you: "{user_message or 'Hello'}"

Your task is to politely, warmly, and conversationally acknowledge their specific query or situation, and explain that you need their booking reference code (e.g. BK-1234) to look up the details and assist them.
Do not sound like a machine. Acknowledge what they are asking about (e.g. tracking their bus, reschedule, cancellation, etc.) naturally and then ask for the code.

CRITICAL REQUIREMENTS:
1. You MUST generate your response ONLY in the following language: {lang_name}.
2. Speak like a professional travel support executive. Avoid repeating greetings or introductory phrases (like "Hello", "How can I help you today?") if the message history indicates the conversation is already in progress.
3. Be concise, polite, and context-aware. Never sound robotic.
{hindi_rule}
{voice_rule}

Recent Conversation History:
{history_str}
"""
        )

        human = HumanMessage(content=f"User request: {user_message or 'Help me'}")

        for chunk in self.llm.stream([system, human]):
            yield chunk