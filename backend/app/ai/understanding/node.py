from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.factory import get_llm
from app.ai.understanding.prompt import UNDERSTANDING_PROMPT
from app.ai.understanding.schema import UnderstandingResult
from app.ai.utils.json_parser import parse_json
from app.ai.intent.schemas import Intent

llm = get_llm()


def understand(message: str, history: list = None) -> UnderstandingResult:
    formatted_history = ""
    if history:
        history_msgs = []
        for msg in history[-5:]:  # look at last 5 messages for context
            role = "Customer" if msg.get("role") == "user" else "Assistant"
            history_msgs.append(f"{role}: {msg.get('message')}")
        formatted_history = "\n".join(history_msgs)

    system_content = UNDERSTANDING_PROMPT
    if formatted_history:
        system_content += f"\n\nRecent Conversation History:\n{formatted_history}\n"

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=message),
    ]

    response = llm.invoke(messages)

    if hasattr(response, "content"):
        response = response.content

    try:

        data = parse_json(response)

        intent_val = data.get("intent")
        if not intent_val or intent_val not in [i.value for i in Intent]:
            data["intent"] = Intent.GENERAL.value

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