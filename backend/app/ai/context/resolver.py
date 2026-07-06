import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.context.prompt import CONTEXT_PROMPT
from app.ai.llm.factory import get_llm

llm = get_llm()


class ContextResolver:

    FOLLOW_UP_KEYWORDS = [
        "destination",
        "source",
        "seat",
        "arrival",
        "departure",
        "bus number",
        "bus",
        "delay",
        "refund",
        "status",
        "cancel it",
        "cancel",
        "driver",
        "eta",
        "time",
        "where",
        "when",
    ]

    def resolve(
        self,
        question: str,
        session,
    ):

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

        prompt = CONTEXT_PROMPT.format(
            context=json.dumps(
            session.last_result,
            indent=2,
            default=str,
        ),
            question=question,
        )

        response = llm.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=question),
            ]
        )

        if hasattr(response, "content"):
            return response.content.strip()

        return str(response)