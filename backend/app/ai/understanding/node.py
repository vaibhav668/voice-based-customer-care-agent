from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm
from app.ai.understanding.prompt import UNDERSTANDING_PROMPT
from app.ai.understanding.schema import UnderstandingResult
from app.ai.utils.json_parser import parse_json
from app.ai.intent.schemas import Intent

llm = get_llm()


def understand(message: str) -> UnderstandingResult:

    messages = [
        SystemMessage(content=UNDERSTANDING_PROMPT),
        HumanMessage(content=message),
    ]

    response = llm.invoke(messages)

    if hasattr(response, "content"):
        response = response.content

    try:

        data = parse_json(response)

        return UnderstandingResult(**data)

    except Exception as e:

        print("=" * 60)
        print("UNDERSTANDING ERROR")
        print(e)
        print(response)
        print("=" * 60)

        return UnderstandingResult(
            intent=Intent.GENERAL,
            confidence=0.0,
            booking_code=None,
            passenger_name=None,
            complaint=None,
            bus_number=None,
        )