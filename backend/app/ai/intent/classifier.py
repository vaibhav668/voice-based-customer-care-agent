from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.intent.prompts import INTENT_PROMPT
from app.ai.schemas.intent import Intent
from app.ai.llm.factory import get_llm

llm = get_llm()


def classify_intent(message: str) -> Intent:

    messages = [
        SystemMessage(
            content="You are an intent classifier."
        ),
        HumanMessage(
            content=INTENT_PROMPT.format(message=message)
        ),
    ]

    response = llm.invoke(messages).strip()

    return Intent(response)