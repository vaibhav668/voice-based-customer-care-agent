import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.context.prompt import CONTEXT_PROMPT
from app.ai.llm.factory import get_llm

llm = get_llm()


class ContextResolver:

    FOLLOW_UP_KEYWORDS = [
        # English terms
        "destination", "source", "seat", "arrival", "departure", "bus number", "bus",
        "delay", "refund", "status", "cancel it", "cancel", "driver", "eta", "time", "where", "when",
        # Hindi / Hinglish / Regional terms
        "samay", "kab", "kahan", "kaha", "aagman", "prashthan", "der", "late", "gaadi", "gadi",
        "pahuchegi", "timing", "seet", "seat", "vapis", "wapasi", "paisa", "paise", "rut", "route"
    ]

    def resolve(
        self,
        question: str,
        session,
        intent: str | None = None,
    ):
        # 1. Do not resolve contextually if user query contains an explicit booking code
        import re
        if re.search(r'\bBK-\d+\b', question, re.IGNORECASE):
            return None

        # 2. Do not resolve contextually if intent is a specific database/policy tool intent
        if intent not in (None, "FOLLOW_UP", "GENERAL", "PROVIDE_BOOKING_CODE"):
            return None

        # No previous tool output
        if not session.last_result:
            return None

        question_lower = question.lower()

        # Only treat genuine follow-up questions as contextual
        if not any(
            keyword in question_lower
            for keyword in self.FOLLOW_UP_KEYWORDS
        ):
            return None

        lang_code = getattr(session, "language", "en")
        hindi_rule = ""
        if lang_code.lower() == "hi":
            hindi_rule = "\n\nCRITICAL HINDI GRAMMAR REQUIREMENT: Since the assistant voice is FEMALE, you MUST consistently use feminine grammatical structures throughout your response (e.g., 'karungi', 'sakti', 'bataungi' instead of 'karunga', 'sakta', 'bataunga'). Never use masculine verb endings for your own actions.\n"

        prompt = CONTEXT_PROMPT.format(
            context=json.dumps(
                session.last_result,
                indent=2,
                default=str,
            ),
            question=question,
        )
        if hindi_rule:
            prompt += hindi_rule

        response = llm.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=f"Answering in language: {lang_code}\nQuestion: {question}"),
            ]
        )

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)